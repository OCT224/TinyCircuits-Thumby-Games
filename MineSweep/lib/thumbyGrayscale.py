from array import array
from machine import Pin, SPI, idle, mem32
from os import stat
from math import sqrt, floor
import utime
from utime import sleep_ms, ticks_diff, ticks_ms, sleep_us
import _thread
from thumbyButton import buttonA, buttonB, buttonU, buttonD, buttonL, buttonR
from thumbySprite import Sprite as _Sprite

emulator = None
try:
    import emulator
except ImportError:
    pass

# The times below are calculated using phase 1 and phase 2 pre-charge
# periods of 1 clock.
# Note that although the SSD1306 datasheet doesn't state it, the 50
# clocks period per row _is_ a constant (datasheets for similar
# controllers from the same manufacturer state this).
# 530kHz is taken to be the highest nominal clock frequency. The
# calculations shown provide the value in seconds, which can be
# multiplied by 1e6 to provide a microsecond value.
# Both values are in microseconds.
_PRE_FRAME_TIME_US = const(785) # 8 rows: (8*(1+1+50)) / 530e3 seconds
_FRAME_TIME_US = const(4709) # 48 rows: (49*(1+1+50)) / 530e3 seconds

# Thread state variables for managing the Grayscale Thread.
_THREAD_STOPPED = const(0)
_THREAD_STARTING = const(1)
_THREAD_RUNNING = const(2)
_THREAD_STOPPING = const(3)

# Indexes into the multipurpose state array, accessing a particular status.
_ST_THREAD = const(0)
_ST_COPY_BUFFS = const(1)
_ST_PENDING_CMD = const(2)
_ST_CONTRAST = const(3)
_ST_INVERT = const(4)

# Screen display size constants
_WIDTH = const(72)
_HEIGHT = const(40)
_BUFF_SIZE = const((_HEIGHT // 8) * _WIDTH)
_BUFF_INT_SIZE = const(_BUFF_SIZE // 4)

class Grayscale:
    ### Grayscale extension of thumby.display retaining compatbility,
    # (matches thumbyGraphics.GraphicsClass but with shading)
    # Most games can be switched to support grayscale with the following:
    #     import thumbyGrayscale
    #     thumby.display = thumbyGrayscale.display
    #     thumbyGrayscale.display.enableGrayscale()
    ###

    # BLACK and WHITE is 0 and 1 to match compatbility with the std Thumby API.
    BLACK = 0
    WHITE = 1
    DARKGRAY = 2
    LIGHTGRAY = 3

    def __init__(self):
        # Public and compatibility variables
        self.width = _WIDTH
        self.height = _HEIGHT
        self.max_x = _WIDTH - 1
        self.max_y = _HEIGHT - 1
        self.lastUpdateEnd = 0
        self.frameRate = 0
        self.display = self # This acts as both the GraphicsClass and SSD1306
        self.contrast = self.brightness
        self.setFont('lib/font5x7.bin', 5, 7, 1)

        # Draw buffers.
        # This comprises of two full buffer lengths.
        # The first section contains black and white compatible
        # with the display buffer from the standard Thumby API,
        # and the second contains the shading to create
        # offwhite (lightgray) or offblack (darkgray).
        self.drawBuffer = bytearray(_BUFF_SIZE*2)
        # The base "buffer" matches compatibility with the std Thumby API.
        self.buffer = memoryview(self.drawBuffer)[:_BUFF_SIZE]
        # The "shading" buffer adds the grayscale
        self.shading = memoryview(self.drawBuffer)[_BUFF_SIZE:]

        # Thred state buffer
        # It's better to avoid using regular variables for thread sychronisation.
        # Instead, elements of an array/bytearray should be used.
        # We're also using a uint32 array here, as this more likely to ensure
        # the atomicity of any element accesses.
        # [thread_state, buff_copy_gate, pending_cmd_gate, constrast_change, inverted]
        self._state = array('I', [_THREAD_STOPPED,0,0,0,0])
        # Buffer to funnel cmds to the thread
        self._pendingCmds = bytearray([0] * 8)

        # Display device configuration
        self._initEmuScreen()
        self._spi = SPI(0, sck=Pin(18), mosi=Pin(19))
        self._dc = Pin(17)
        self._cs = Pin(16)
        self._res = Pin(20)
        self._res.init(Pin.OUT, value=1)
        self._spi.init(baudrate=100 * 1000 * 1000, polarity=0, phase=0)

        # Display driver subframe buffers.
        # These essentially combine into one framebuffer,
        # but are split into three buffers that hit the display
        # at different subframe intervals.
        self._subframes = array('O', [bytearray(_BUFF_SIZE),
            bytearray(_BUFF_SIZE), bytearray(_BUFF_SIZE)])

        # Timing and display synchronisation commands.
        #
        # NOTE: The method used to create reduced flicker greyscale using
        # the SSD1306 uses certain assumptions about the internal behaviour
        # of the controller. Even though the behaviour seems to back up
        # those assumptions, it is possible that the assumptions are
        # incorrect but the desired result is achieved anyway. To simplify
        # things, the following comments are written as if the assumptions
        # _are_ correct.
        #
        # We keep the display synchronised by resetting the row counter
        # before each frame and then outputting a frame of 57 rows.
        # This is 17 rows past the 40 of the actual display.
        #
        # Prior to loading in the frame we park the row counter at row 0
        # and wait for the nominal time for 8 rows to be output. This
        # seems to provide enough time for the row counter to reach row 0
        # before it sticks there. Note: the row counter may jump then stick.
        #
        # The 'parking' is done by setting the number of rows (aka
        # 'multiplex ratio') to 1 row. This is an invalid setting
        # according to the datasheet but seems to still have the desired
        # effect.
        # 0xa8,0    Set multiplex ratio to 1
        # 0xd3,52   Set display offset to 52
        self._preFrameCmds = bytearray([0xa8,0, 0xd3,52])
        # Once the frame has been loaded into the display controller's
        # GDRAM, we set the controller to output 57 rows, and then delay
        # for the nominal time for 48 rows to be output.
        # Considering the 17 row 'buffer space' after the real 40 rows,
        # that puts us around halfway between the end of the display, and
        # the row at which it would wrap around.
        # By having 8.5 rows either side of the nominal timing, we can
        # absorb any variation in the frequency of the display controller's
        # RC oscillator as well as any timing offsets introduced by the
        # Python code.
        # 0xd3,x    Set display offset. Since rows are scanned in reverse,
        #           the calculation must work backwards from the last
        #.          controller row.
        # 0xa8,57-1 Set multiplex ratio to 57
        self._postFrameCmds = bytearray([0xd3,_HEIGHT+(64-57), 0xa8,57-1])

        # Brightness modulation.
        # We enhance the greys by modulating the contrast,
        # limited to brightness setting from thumby.cfg
        # 0x81,<val>    GPU will set Bank0 contrast value to <val>
        self._postFrameAdj = array('O', bytearray([0x81,0]) for i in range(3))
        self._postFrameAdjSrc = bytearray(3)
        self._brightness = 127
        try:
            with open("thumby.cfg", "r") as fh:
                _, _, conf = fh.read().partition("brightness,")
                b = int(conf.split(',')[0])
                # Set to the relevant brightness level
                self._brightness = 0 if b==0 else 28 if b==1 else 127
        except (OSError, ValueError):
            pass
        self.brightness(self._brightness)

    # Allow use of 'with' for manaing the GPU state
    def __enter__(self):
        self.enableGrayscale()
        return self
    def __exit__(self, type, value, traceback):
        self.disableGrayscale()


    ## Display device functions ##


    @micropython.viper
    def _initEmuScreen(self):
        if not emulator:
            return
        # Register draw buffer with emulator
        Pin(2, Pin.OUT) # Ready display handshake pin
        emulator.screen_breakpoint(ptr16(self.drawBuffer))
        self._clearEmuFunctions()
    def _clearEmuFunctions(self):
        # Disable device controller functions
        def _disabled(*arg, **kwdarg):
            pass
        self.invert = _disabled
        self.reset = _disabled
        self.poweron = _disabled
        self.poweroff = _disabled
        self.init_display = _disabled
        self.write_cmd = _disabled

    def reset(self):
        self._res(1)
        sleep_ms(1)
        self._res(0)
        sleep_ms(10)
        self._res(1)
        sleep_ms(10)

    def init_display(self):
        self._dc(0)

        if not self._display_initialised:
            self._display_initialised = 1
            self.reset()
            self._cs(0)
            self._dc(0)
            # Usual initialisation, except with shortest pre-charge periods
            # and highest clock frequency:
            # 0xae          Display Off
            # 0x20,0x00     Set horizontal addressing mode
            # 0x40          Set display start line to 0
            # 0xa1          Set segment remap mode 1
            # 0xa8,63       Set multiplex ratio to 64 (will be changed later)
            # 0xc8          Set COM output scan direction 1
            # 0xd3,0        Set display offset to 0 (will be changed later)
            # 0xda,0x12     Set COM pins hw config: alt config, disable left/right remap
            # 0xd5,0xf0     Set clk div ratio = 1, and osc freq = ~370kHz
            # 0xd9,0x11     Set pre-charge periods: phase 1 = 1 , phase 2 = 1
            # 0xdb,0x20     Set Vcomh deselect level = 0.77 x Vcc
            # 0x81,0x7f     Set Bank0 contrast to 127 (will be changed later)
            # 0xa4          Do not enable entire display (i.e. use GDRAM)
            # 0xa6          Normal (not inverse) display
            # 0x8d,0x14     Charge bump setting: enable charge pump during display on
            # 0xad,0x30     Select internal 30uA Iref (max Iseg=240uA) during display on
            # 0xaf          Set display on
            self._spi.write(bytearray([
                0xae, 0x20,0x00, 0x40, 0xa1, 0xa8,63, 0xc8, 0xd3,0, 0xda,0x12,
                0xd5,0xf0, 0xd9,0x11, 0xdb,0x20, 0x81,0x7f, 0xa4, 0xa6, 0x8d,0x14,
                0xad,0x30, 0xaf]))
            # clear the entire GDRAM
            self._dc(1)
            zero32 = bytearray(32)
            for _ in range(32):
                self._spi.write(zero32)
            self._dc(0)
            # set the GDRAM window
            # 0x21,28,99    Set column start (28) and end (99) addresses
            # 0x22,0,4      Set page start (0) and end (4) addresses0
            self._spi.write(bytearray([0x21,28,99, 0x22,0,4]))

        # (Re)Initialise the display for monocrhome timings
        if self._state[_ST_THREAD] == _THREAD_STOPPED:
            # Reinitialise to the normal configuration. Copied from ssd1306.py
            # 0xa8,0        Set multiplex ratio to 0 (pausing updates)
            # 0xd3,52       Set display offset to 52
            # 0xd5,0x80     Set clk div ratio to standard Thumby levels
            # 0xd9,0xf1     Set pre-charge periods to standard Thumby levels
            self._spi.write(bytearray([
                0xa8,0, 0xd3,52, 0xd5,0x80, 0xd9,0xf1]))
            sleep_us(_FRAME_TIME_US*3)
            # 0xa8,39       Set multiplex ratio to height (releasing updates)
            # 0xd3,0        Set display offset to 0
            self._spi.write(bytearray([0xa8,_HEIGHT-1,0xd3,0]))
            if self._state[_ST_INVERT]:
                self.write_cmd(0xa6 | 1) # Resume device color inversion
            return

        self.write_cmd(0xa6) # Stop device color inversion for GPU
        # Initialise the display for grayscale timings
        # Usual initialisation, except with shortest pre-charge periods
        # multiplex of 0, and highest clock frequency:
        # 0xae          Display Off
        # 0xa8,0        Set multiplex ratio to 0 (will be changed later)
        # 0xd3,0        Set display offset to 0 (will be changed later)
        # 0xd5,0xf0     Set clk div ratio = 1, and osc freq = ~370kHz
        # 0xd9,0x11     Set pre-charge periods: phase 1 = 1 , phase 2 = 1
        # 0xaf           Set display on
        self._spi.write(bytearray([
            0xae, 0xa8,0, 0xd3,0, 0xd5,0xf0, 0xd9,0x11, 0xaf]))
    _display_initialised = 0

    @micropython.viper
    def show(self):
        state = ptr32(self._state)
        if state[_ST_THREAD] == _THREAD_RUNNING:
            state[_ST_COPY_BUFFS] = 1
            while state[_ST_COPY_BUFFS] != 0:
                idle()
        elif emulator:
            mem32[0xD0000000+0x01C] = 1<<2
        else:
            self._dc(1)
            self._spi.write(self.buffer)

    @micropython.native
    def show_async(self):
        state = ptr32(self._state)
        if state[_ST_THREAD] == _THREAD_RUNNING:
            state[_ST_COPY_BUFFS] = 1
        else:
            self.show()

    @micropython.native
    def write_cmd(self, cmd):
        ### Send display controller commands ###
        if isinstance(cmd, list):
            cmd = bytearray(cmd)
        elif not isinstance(cmd, bytearray):
            cmd = bytearray([cmd])

        # Handle when GPU isn't active
        if self._state[_ST_THREAD] != _THREAD_RUNNING:
            self._dc(0)
            self._spi.write(cmd)
            return

        # GPU is active - ferry the commans to the thread
        pendingCmds = self._pendingCmds
        # We can't just break up the longer list of commands automatically,
        # as we might end up separating a command and its parameter(s).
        assert len(cmd) <= len(pendingCmds), "Display commands too long"
        i = 0
        while i < len(cmd):
            pendingCmds[i] = cmd[i]
        # Fill the rest of the bytearray with display controller NOPs
        while i < len(pendingCmds):
            pendingCmds[i] = 0x3e
            i += 1
        # Notify GPU and wait
        self._state[_ST_PENDING_CMD] = 1
        while self._state[_ST_PENDING_CMD]:
            idle()

    def poweroff(self):
        self.write_cmd(0xae)
    def poweron(self):
        self.write_cmd(0xaf)

    @micropython.viper
    def invert(self, invert: int):
        state = ptr32(self._state)
        invert = invert & 1
        state[_ST_INVERT] = invert # GPU color inversion
        state[_ST_COPY_BUFFS] = 1 # Trigger display of inversion
        if state[_ST_THREAD] != _THREAD_RUNNING:
            self.write_cmd(0xa6 | invert) # Device controller inversion

    def enableGrayscale(self):
        ### Activate grayscale in the display (Gray Processing Unit).
        # Takes over the second core.
        # When the GPU is not running, the display will only show
        # black and white.
        ###
        if emulator:
            # Activate grayscale emulation
            emulator.screen_breakpoint(1)
            self.show()
            return

        if self._state[_ST_THREAD] == _THREAD_RUNNING:
            return

        # Start the GPU thread
        self._state[_ST_THREAD] = _THREAD_STARTING
        self.init_display()
        _thread.stack_size(2048) # minimum stack size for RP2040 upython port
        _thread.start_new_thread(self._display_thread, ())

        # Wait for the thread to successfully settle into a running state
        while self._state[_ST_THREAD] != _THREAD_RUNNING:
            idle()


    @micropython.viper
    def _display_thread(self):
        ### GPU (Gray Processing Unit) thread function ###
        # cache various instance variables, buffers, and functions/methods

        postFrameAdjSrc = ptr8(self._postFrameAdjSrc)
        state = ptr32(self._state)

        buffers:ptr32 = ptr32(array('L', [ptr8(self._subframes[0]), ptr8(self._subframes[1]), ptr8(self._subframes[2])]))
        postFrameAdj:ptr32 = ptr32(array('L', [ptr8(self._postFrameAdj[0]), ptr8(self._postFrameAdj[1]), ptr8(self._postFrameAdj[2])]))
        preFrameCmds:ptr8 = ptr8(self._preFrameCmds)
        postFrameCmds:ptr8 = ptr8(self._postFrameCmds)
        pendingCmds:ptr8 = ptr8(self._pendingCmds)

        spi0:ptr32 = ptr32(0x4003c000)
        tmr:ptr32 = ptr32(0x40054000)
        sio:ptr32 = ptr32(0xd0000000)

        dBuf = ptr32(self.drawBuffer)
        b1 = ptr32(self._subframes[0]); b2 = ptr32(self._subframes[1]); b3 = ptr32(self._subframes[2])

        state[_ST_THREAD] = _THREAD_RUNNING
        while state[_ST_THREAD] == _THREAD_RUNNING:
            # This is the main GPU loop.
            # We cycle through each of the 3 display subframe buffers,
            # sending the framebuffer data and various commands.
            fn = 0
            while fn < 3:
                time_out = tmr[10] + _PRE_FRAME_TIME_US
                # the 'dc' output is used to switch the controller to receive
                # commands (0) or frame data (1)
                sio[6] = 1 << 17 # dc(0)

                # send the pre-frame commands to 'park' the row counter
                # spi_write(preFrameCmds)
                i = 0
                while i < 4:
                    while (spi0[3] & 2) == 0: pass          # while !(SPI0->SR & SPI_SSPSR_TNF_BITS): pass
                    spi0[2] = preFrameCmds[i]               # SPI0->DR = buff[i]
                    i += 1
                while (spi0[3] & 4) == 4: i = spi0[2]       # while SPI0->SR & SPI_SSPSR_RNE_BITS: read SPI0->DR
                while (spi0[3] & 0x10) == 0x10: pass        # while SPI0->SR & SPI_SSPSR_BSY_BITS: pass
                while (spi0[3] & 4) == 4: i = spi0[2]       # while SPI0->SR & SPI_SSPSR_RNE_BITS: read SPI0->DR

                sio[5] = 1 << 17 # dc(1)
                # and then send the frame
                # spi_write(buffers[fn])
                i = 0
                spibuff:ptr8 = ptr8(buffers[fn])
                while i < 360:
                    while (spi0[3] & 2) == 0: pass
                    spi0[2] = spibuff[i]
                    i += 1
                while (spi0[3] & 4) == 4: i = spi0[2]
                while (spi0[3] & 0x10) == 0x10: pass
                while (spi0[3] & 4) == 4: i = spi0[2]

                sio[6] = 1 << 17 # dc(0)
                # send the first instance of the contrast adjust command
                #spi_write(postFrameAdj[fn])
                i = 0
                spibuff:ptr8 = ptr8(postFrameAdj[fn])
                while i < 2:
                    while (spi0[3] & 2) == 0: pass
                    spi0[2] = spibuff[i]
                    i += 1
                while (spi0[3] & 4) == 4: i = spi0[2]
                while (spi0[3] & 0x10) == 0x10: pass
                while (spi0[3] & 4) == 4: i = spi0[2]

                # wait for the pre-frame time to complete
                while (tmr[10] - time_out) < 0:
                    pass

                time_out = tmr[10] + _FRAME_TIME_US

                # now send the post-frame commands to display the frame
                # spi_write(postFrameCmds)
                i = 0
                while i < 4:
                    while (spi0[3] & 2) == 0: pass
                    spi0[2] = postFrameCmds[i]
                    i += 1
                # and adjust the contrast for the specific frame number again.
                # If we do not do this twice, the screen can glitch.
                # spi_write(postFrameAdj[fn])
                i = 0
                spibuff:ptr8 = ptr8(postFrameAdj[fn])
                while i < 2:
                    while (spi0[3] & 2) == 0: pass
                    spi0[2] = spibuff[i]
                    i += 1
                while (spi0[3] & 4) == 4: i = spi0[2]
                while (spi0[3] & 0x10) == 0x10: pass
                while (spi0[3] & 4) == 4: i = spi0[2]

                # Tasks that only happen after the last subframe
                if fn == 2:
                    # Check if there's a pending frame copy required.
                    # We only copy the paint framebuffers to the display
                    # framebuffers on the last frame to avoid screen-tearing.
                    if state[_ST_COPY_BUFFS] != 0:
                        # By using using ptr32 vars we copy 4 bytes at a time
                        i = 0
                        j = _BUFF_INT_SIZE
                        inv = -1 if state[_ST_INVERT] else 0
                        while i < _BUFF_INT_SIZE:
                            v1 = dBuf[i] ^ inv
                            v2 = dBuf[j]
                            # This remaps to the different buffer format.
                            b1[i] = v1 | v2 # white, lightgray and darkgray
                            b2[i] = v1 # white and lightgray
                            b3[i] = v1 & (v1^v2) # white only
                            i += 1
                            j += 1
                        state[_ST_COPY_BUFFS] = 0
                    # Check if there's a pending contrast/brightness change
                    if state[_ST_CONTRAST]:
                        # Copy in the new contrast adjustments
                        ptr8(postFrameAdj[0])[1] = postFrameAdjSrc[0]
                        ptr8(postFrameAdj[1])[1] = postFrameAdjSrc[1]
                        ptr8(postFrameAdj[2])[1] = postFrameAdjSrc[2]
                        state[_ST_CONTRAST] = 0
                    # Check if there are pending display controller commands
                    elif state[_ST_PENDING_CMD]:
                        #spi_write(pendingCmds)
                        i = 0
                        while i < 8:
                            while (spi0[3] & 2) == 0: pass
                            spi0[2] = pendingCmds[i]
                            i += 1
                        while (spi0[3] & 4) == 4: i = spi0[2]
                        while (spi0[3] & 0x10) == 0x10: pass
                        while (spi0[3] & 4) == 4: i = spi0[2]
                        state[_ST_PENDING_CMD] = 0

                # wait for frame time to complete
                while (tmr[10] - time_out) < 0:
                    pass

                fn += 1

        # Announce the thread is done
        state[_ST_THREAD] = _THREAD_STOPPED


    def disableGrayscale(self):
        ### Disable grayscale, stopping the running thread.
        # If modeGPU is set to 1, it will not reset the display
        # controller configuration.
        ###
        if emulator:
            # Disable grayscale emulation
            emulator.screen_breakpoint(0)
            self.show()
            return

        if self._state[_ST_THREAD] == _THREAD_RUNNING:
            self._state[_ST_THREAD] = _THREAD_STOPPING
            while self._state[_ST_THREAD] != _THREAD_STOPPED:
                idle()
            # Refresh the image to the B/W form
            self.init_display()
            self.show()
            # Change back to the original (unmodulated) brightness setting
            self.brightness(self._brightness)


    ## GraphicsClass functions ##


    @micropython.native
    def setFPS(self, newFrameRate):
        self.frameRate = newFrameRate

    @micropython.viper
    def fill(self, colour:int):
        dBuf1 = ptr32(self.drawBuffer)
        dBuf2 = ptr32(self.shading)
        f1 = -1 if colour & 1 else 0
        f2 = -1 if colour & 2 else 0
        i = 0
        while i < _BUFF_INT_SIZE:
            dBuf1[i] = f1 # Black/White layer
            dBuf2[i] = f2 # Shading layer
            i += 1

    @micropython.viper
    def brightness(self, c: int):
        c = 0 if c<0 else 127 if c>127 else c
        state = ptr32(self._state)
        postFrameAdj = self._postFrameAdj
        postFrameAdjSrc = ptr8(self._postFrameAdjSrc)

        # Provide 3 different subframe levels for the GPU
        # Low (0): 0, 5, 15
        # Mid (28): 4, 42, 173
        # High (127):  9, 84, 255
        cc = int(floor(sqrt(c<<17)))
        postFrameAdjSrc[0] = (cc*30>>12)+6
        postFrameAdjSrc[1] = (cc*72>>12)+14
        c3 = (cc*340>>12)+20
        postFrameAdjSrc[2] = c3 if c3 < 255 else 255

        # Apply to display, GPU, and emulator
        if state[_ST_THREAD] == _THREAD_RUNNING:
            state[_ST_CONTRAST] = 1
        else:
            # Copy in the new contrast adjustments for when the GPU starts
            postFrameAdj[0][1] = postFrameAdjSrc[0]
            postFrameAdj[1][1] = postFrameAdjSrc[1]
            postFrameAdj[2][1] = postFrameAdjSrc[2]
            # Apply the contrast directly to the display
            if emulator:
                emulator.brightness_breakpoint(c)
            else:
                self.write_cmd([0x81, c])
        # Save the intended contrast for whenever the GPU stops
        self._brightness = c <<1|1

    @micropython.native
    def update(self):
        self.show()
        if self.frameRate > 0:
            frameTimeMs = 1000 // self.frameRate
            lastUpdateEnd = self.lastUpdateEnd
            frameTimeRemaining = frameTimeMs - ticks_diff(ticks_ms(), lastUpdateEnd)
            while frameTimeRemaining > 1:
                buttonA.update()
                buttonB.update()
                buttonU.update()
                buttonD.update()
                buttonL.update()
                buttonR.update()
                sleep_ms(1)
                frameTimeRemaining = frameTimeMs - ticks_diff(ticks_ms(), lastUpdateEnd)
            while frameTimeRemaining > 0:
                frameTimeRemaining = frameTimeMs - ticks_diff(ticks_ms(), lastUpdateEnd)
        self.lastUpdateEnd = ticks_ms()

    @micropython.viper
    def drawFilledRectangle(self, x:int, y:int, width:int, height:int, colour:int):
        if x >= _WIDTH or y >= _HEIGHT or width <= 0 or height <= 0:
            return
        if x < 0:
            width += x
            x = 0
        if y < 0:
            height += y
            y = 0
        x2 = x + width
        if x2 > _WIDTH:
            x2 = _WIDTH
            width = _WIDTH - x
        if y + height > _HEIGHT:
            height = _HEIGHT - y

        dBuff1 = ptr8(self.drawBuffer)
        dBuff2 = ptr8(self.shading)

        o = (y >> 3) * _WIDTH
        oe = o + x2
        o += x
        strd = _WIDTH - width
        c1 = colour & 1
        c2 = colour & 2

        yb = y & 7
        ybh = 8 - yb
        if height <= ybh:
            m = ((1 << height) - 1) << yb
        else:
            m = 0xff << yb
        im = 255-m
        while o < oe:
            if c1:
                dBuff1[o] |= m
            else:
                dBuff1[o] &= im
            if c2:
                dBuff2[o] |= m
            else:
                dBuff2[o] &= im
            o += 1
        height -= ybh
        v1 = 0xff if c1 else 0
        v2 = 0xff if c2 else 0
        while height >= 8:
            o += strd
            oe += _WIDTH
            while o < oe:
                dBuff1[o] = v1
                dBuff2[o] = v2
                o += 1
            height -= 8
        if height > 0:
            o += strd
            oe += _WIDTH
            m = (1 << height) - 1
            im = 255-m
            while o < oe:
                if c1:
                    dBuff1[o] |= m
                else:
                    dBuff1[o] &= im
                if c2:
                    dBuff2[o] |= m
                else:
                    dBuff2[o] &= im
                o += 1

    @micropython.viper
    def drawRectangle(self, x:int, y:int, width:int, height:int, colour:int):
        dfr = self.drawFilledRectangle
        dfr(x, y, width, 1, colour) # Top
        dfr(x, y+height-1, width, 1, colour) # Bottom
        dfr(x, y, 1, height, colour) # Left
        dfr(x+width-1, y, 1, height, colour) # Right

    @micropython.viper
    def setPixel(self, x:int, y:int, colour:int):
        if x < 0 or x >= _WIDTH or y < 0 or y >= _HEIGHT:
            return
        o = (y >> 3) * _WIDTH + x
        m = 1 << (y & 7)
        im = 255-m
        dBuff = ptr8(self.drawBuffer)
        if colour & 1:
            dBuff[o] |= m
        else:
            dBuff[o] &= im
        if colour & 2:
            dBuff[o+_BUFF_SIZE] |= m
        else:
            dBuff[o+_BUFF_SIZE] &= im

    @micropython.viper
    def getPixel(self, x:int, y:int) -> int:
        if x < 0 or x >= _WIDTH or y < 0 or y >= _HEIGHT:
            return 0
        o = (y >> 3) * _WIDTH + x
        m = 1 << (y & 7)
        dBuff = ptr8(self.drawBuffer)
        colour = 0
        if dBuff[o] & m:
            colour = 1
        if dBuff[o+_BUFF_SIZE] & m:
            colour |= 2
        return colour

    @micropython.viper
    def drawLine(self, x0:int, y0:int, x1:int, y1:int, colour:int):
        if (x0==x1):
            self.drawFilledRectangle(x0, y0, 1, y1-y0, colour)
            return
        elif (y0==y1):
            self.drawFilledRectangle(x0, y0, x1-x0, 1, colour)
            return
        dx = x1 - x0
        dy = y1 - y0
        sx = 1
        # y increment is always 1
        if dy < 0:
            x0,x1 = x1,x0
            y0,y1 = y1,y0
            dy = 0 - dy
            dx = 0 - dx
        if dx < 0:
            dx = 0 - dx
            sx = -1
        x = x0
        y = y0

        dBuf1 = ptr8(self.drawBuffer)
        dBuf2 = ptr8(self.shading)

        o = (y >> 3) * _WIDTH + x
        m = 1 << (y & 7)
        im = 255-m
        c1 = colour & 1
        c2 = colour & 2

        if dx > dy:
            err = dx >> 1
            while x != x1+1:
                if 0 <= x < _WIDTH and 0 <= y < _HEIGHT:
                    if c1:
                        dBuf1[o] |= m
                    else:
                        dBuf1[o] &= im
                    if c2:
                        dBuf2[o] |= m
                    else:
                        dBuf2[o] &= im
                err -= dy
                if err < 0:
                    y += 1
                    m <<= 1
                    if m & 0x100:
                        o += _WIDTH
                        m = 1
                        im = 0xfe
                    else:
                        im = 255-m
                    err += dx
                x += sx
                o += sx
        else:
            err = dy >> 1
            while y != y1+1:
                if 0 <= x < _WIDTH and 0 <= y < _HEIGHT:
                    if c1:
                        dBuf1[o] |= m
                    else:
                        dBuf1[o] &= im
                    if c2:
                        dBuf2[o] |= m
                    else:
                        dBuf2[o] &= im
                err -= dx
                if err < 0:
                    x += sx
                    o += sx
                    err += dy
                y += 1
                m <<= 1
                if m & 0x100:
                    o += _WIDTH
                    m = 1
                    im = 0xfe
                else:
                    im = 255-m

    def setFont(self, fontFile, width, height, space):
        sz = stat(fontFile)[6]
        self.font_bmap = bytearray(sz)
        with open(fontFile, 'rb') as fh:
            fh.readinto(self.font_bmap)
        self.font_width = width
        self.font_height = height
        self.font_space = space
        self.font_glyphcnt = sz // width

    @micropython.viper
    def drawText(self, stringToPrint, x:int, y:int, colour:int):
        dBuff = ptr8(self.drawBuffer)
        font_bmap = ptr8(self.font_bmap)
        font_width = int(self.font_width)
        font_space = int(self.font_space)
        font_glyphcnt = int(self.font_glyphcnt)
        sm1o = 0xff if colour & 1 else 0
        sm1a = 255 - sm1o
        sm2o = 0xff if colour & 2 else 0
        sm2a = 255 - sm2o
        ou = (y >> 3) * _WIDTH + x
        ol = ou + _WIDTH
        shu = y & 7
        shl = 8 - shu
        for c in memoryview(stringToPrint):
            if isinstance(c, str):
                co = int(ord(c)) - 0x20
            else:
                co = int(c) - 0x20
            if co < font_glyphcnt:
                gi = co * font_width
                gx = 0
                while gx < font_width:
                    if 0 <= x < _WIDTH:
                        gb = font_bmap[gi + gx]
                        gbu = gb << shu
                        gbl = gb >> shl
                        if 0 <= ou < 360:
                            # paint upper byte
                            dBuff[ou] = (dBuff[ou] | (gbu & sm1o)) & 255-(gbu & sm1a)
                            dBuff[ou+_BUFF_SIZE] = (dBuff[ou+_BUFF_SIZE] | (gbu & sm2o)) & 255-(gbu & sm2a)
                        if (shl != 8) and (0 <= ol < 360):
                            # paint lower byte
                            dBuff[ol] = (dBuff[ol] | (gbl & sm1o)) & 255-(gbl & sm1a)
                            dBuff[ol+_BUFF_SIZE] = (dBuff[ol+_BUFF_SIZE] | (gbl & sm2o)) & 255-(gbl & sm2a)
                    ou += 1
                    ol += 1
                    x += 1
                    gx += 1
            ou += font_space
            ol += font_space
            x += font_space

    @micropython.viper
    def blit(self, sprtptr:ptr8, x:int, y:int, width:int, height:int, key:int, mirrorX:int, mirrorY:int):
        self.blitSHD(sprtptr, 0, x, y, width, height, key, mirrorX, mirrorY)

    @micropython.viper
    def blitSHD(self, sprtptr:ptr8, src2:ptr8, x:int, y:int, width:int, height:int, key:int, mirrorX:int, mirrorY:int):
        if x+width < 0 or x >= _WIDTH:
            return
        if y+height < 0 or y >= _HEIGHT:
            return

        stride = width

        srcx = srcy = 0
        dstx = x; dsty = y
        sdx = 1
        if mirrorX:
            sdx = -1
            srcx += width - 1
            if dstx < 0:
                srcx += dstx
                width += dstx
                dstx = 0
        else:
            if dstx < 0:
                srcx = 0 - dstx
                width += dstx
                dstx = 0
        if dstx+width > _WIDTH:
            width = _WIDTH - dstx
        if mirrorY:
            srcy = height - 1
            if dsty < 0:
                srcy += dsty
                height += dsty
                dsty = 0
        else:
            if dsty < 0:
                srcy = 0 - dsty
                height += dsty
                dsty = 0
        if dsty+height > _HEIGHT:
            height = _HEIGHT - dsty

        srco = (srcy >> 3) * stride + srcx
        srcm = 1 << (srcy & 7)

        dsto = (dsty >> 3) * _WIDTH + dstx
        dstm = 1 << (dsty & 7)
        dstim = 255 - dstm

        dBuf1 = ptr8(self.drawBuffer)
        dBuf2 = ptr8(self.shading)
        shading = 2 if int(src2) else 0
        while height != 0:
            srcco = srco
            dstco = dsto
            i = width
            while i != 0:
                v = 0
                if sprtptr[srcco] & srcm:
                    v = 1
                if src2[srcco] & srcm:
                    v |= shading
                if (key == -1) or (v != key):
                    if v & 1:
                        dBuf1[dstco] |= dstm
                    else:
                        dBuf1[dstco] &= dstim
                    if v & 2:
                        dBuf2[dstco] |= dstm
                    else:
                        dBuf2[dstco] &= dstim
                srcco += sdx
                dstco += 1
                i -= 1
            dstm <<= 1
            if dstm & 0x100:
                dsto += _WIDTH
                dstm = 1
                dstim = 0xfe
            else:
                dstim = 255 - dstm
            if mirrorY:
                srcm >>= 1
                if srcm == 0:
                    srco -= stride
                    srcm = 0x80
            else:
                srcm <<= 1
                if srcm & 0x100:
                    srco += stride
                    srcm = 1
            height -= 1

    @micropython.native
    def drawSprite(self, s):
        self.blitSHD(s.bitmap, s.bitmapSHD if isinstance(s, Sprite) else 0,
            s.x, s.y, s.width, s.height, s.key, s.mirrorX, s.mirrorY)

    @micropython.viper
    def blitWithMask(self, sprtptr:ptr8, x:int, y:int, width:int, height:int, key:int, mirrorX:int, mirrorY:int, mask:ptr8):
        self.blitWithMaskSHD(sprtptr, 0, x, y, width, height, key, mirrorX, mirrorY, mask)

    @micropython.viper
    def blitWithMaskSHD(self, sprtptr:ptr8, src2:ptr8, x:int, y:int, width:int, height:int, key:int, mirrorX:int, mirrorY:int, mask:ptr8):
        if x+width < 0 or x >= _WIDTH:
            return
        if y+height < 0 or y >= _HEIGHT:
            return

        stride = width

        srcx = srcy = 0
        dstx = x ; dsty = y
        sdx = 1
        if mirrorX:
            sdx = -1
            srcx += width - 1
            if dstx < 0:
                srcx += dstx
                width += dstx
                dstx = 0
        else:
            if dstx < 0:
                srcx = 0 - dstx
                width += dstx
                dstx = 0
        if dstx+width > _WIDTH:
            width = _WIDTH - dstx
        if mirrorY:
            srcy = height - 1
            if dsty < 0:
                srcy += dsty
                height += dsty
                dsty = 0
        else:
            if dsty < 0:
                srcy = 0 - dsty
                height += dsty
                dsty = 0
        if dsty+height > _HEIGHT:
            height = _HEIGHT - dsty

        srco = (srcy >> 3) * stride + srcx
        srcm = 1 << (srcy & 7)

        dsto = (dsty >> 3) * _WIDTH + dstx
        dstm = 1 << (dsty & 7)
        dstim = 255 - dstm

        dBuf1 = ptr8(self.drawBuffer)
        dBuf2 = ptr8(self.shading)
        shading = int(src2)
        while height != 0:
            srcco = srco
            dstco = dsto
            i = width
            while i != 0:
                if (mask[srcco] & srcm) == 0:
                    if sprtptr[srcco] & srcm:
                        dBuf1[dstco] |= dstm
                    else:
                        dBuf1[dstco] &= dstim
                    if shading:
                        if src2[srcco] & srcm:
                            dBuf2[dstco] |= dstm
                        else:
                            dBuf2[dstco] &= dstim
                    else:
                        dBuf2[dstco] ^= dstm
                srcco += sdx
                dstco += 1
                i -= 1
            dstm <<= 1
            if dstm & 0x100:
                dsto += _WIDTH
                dstm = 1
                dstim = 0xfe
            else:
                dstim = 255 - dstm
            if mirrorY:
                srcm >>= 1
                if srcm == 0:
                    srco -= stride
                    srcm = 0x80
            else:
                srcm <<= 1
                if srcm & 0x100:
                    srco += stride
                    srcm = 1
            height -= 1

    @micropython.native
    def drawSpriteWithMask(self, s, m):
        self.blitWithMaskSHD(
            s.bitmap, s.bitmapSHD if isinstance(s, Sprite) else 0,
            s.x, s.y, s.width, s.height, s.key, s.mirrorX, s.mirrorY, m.bitmap)


class Sprite(_Sprite):
    ### Extends the Sprite with grayscale support.
    # Pass in the shadingData in with bitmapData optionally as a tuple.
    # 1 sets white to lightgray and black to darkgray.
    ###
    @micropython.native
    def __init__(self, width, height, bitmapData, x=0, y=0, key=-1, mirrorX=False, mirrorY=False):
        shadingData = None
        if type(bitmapData) == tuple:
            bitmapData, shadingData = bitmapData
        super().__init__(width, height, bitmapData, x, y, key, mirrorX, mirrorY)
        self.bitmapSourceSHD = shadingData
        if type(self.bitmapSourceSHD)==str:
            self.bitmapSHD = bytearray(self.bitmapByteCount)
            self.fileSHD = open(self.bitmapSourceSHD,'rb')
            self.fileSHD.readinto(self.bitmapSHD)
            assert(self.frameCount == stat(self.bitmapSourceSHD)[6] // self.bitmapByteCount)
        elif type(self.bitmapSourceSHD)==bytearray:
            self.bitmapSHD = memoryview(self.bitmapSourceSHD)[0:self.bitmapByteCount]
            assert(self.frameCount == len(self.bitmapSourceSHD) // self.bitmapByteCount)

    @micropython.native
    def setFrame(self, frame):
        prevFrame = self.currentFrame
        super().setFrame(frame)
        if(prevFrame != self.currentFrame):
            offset=self.bitmapByteCount*self.currentFrame
            if type(self.bitmapSourceSHD)==str:
                self.fileSHD.seek(offset)
                self.fileSHD.readinto(self.bitmapSHD)
            elif type(self.bitmapSourceSHD)==bytearray:
                self.bitmapSHD = memoryview(self.bitmapSourceSHD)[offset:offset+self.bitmapByteCount]

display = Grayscale()
