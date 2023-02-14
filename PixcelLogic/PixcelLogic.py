import time
import thumby
import math
import sys
# BITMAP: width: 70, height: 40
keyvisual = bytearray([0,252,250,246,238,222,190,126,254,254,254,254,254,0,254,58,58,34,254,250,250,250,254,250,250,250,254,250,250,250,254,250,226,242,254,250,250,226,254,250,250,250,254,250,250,250,254,250,250,250,254,250,250,250,0,255,255,255,5,117,65,85,5,255,255,255,255,254,254,254,
            0,159,159,159,159,159,159,159,158,157,155,151,143,0,63,34,35,35,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,0,253,193,253,255,193,255,193,251,193,255,193,213,255,255,255,
            0,255,142,143,143,255,238,204,204,255,136,136,140,0,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,255,255,255,255,162,170,40,255,255,255,127,255,255,255,255,
            0,255,136,136,136,255,255,255,255,255,255,255,255,0,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,255,255,255,255,138,186,8,255,255,255,255,255,255,255,255,
            0,255,136,136,136,255,143,143,143,255,143,175,143,0,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,255,255,255,255,131,187,130,255,255,255,255,255,255,255,255])
# BITMAP: width: 72, height: 40
puzzleVisual = bytearray([0,252,250,246,238,222,190,126,254,254,254,254,254,0,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,0,255,255,255,255,255,255,5,117,65,85,5,255,255,255,255,255,255,
            0,159,159,159,159,159,159,159,158,157,155,151,143,0,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,0,255,255,253,193,253,255,193,127,65,123,193,255,193,213,213,255,255,
            0,255,255,255,255,255,255,255,255,255,255,255,255,0,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,255,255,255,255,255,255,255,16,215,16,255,255,255,255,255,255,255,
            0,255,255,255,255,255,255,255,255,255,255,255,255,0,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,255,255,255,255,255,255,255,4,117,4,255,255,255,255,255,255,255,
            0,255,255,255,255,255,255,255,255,255,255,255,255,0,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,119,119,119,0,255,255,255,255,255,255,255,193,221,193,255,255,255,255,255,255,255])
# BITMAP: width: 14, height: 40
heightBox = bytearray([0,252,250,246,238,222,190,126,254,254,254,254,254,0,
           0,159,159,159,159,159,159,159,158,157,155,151,143,0,
           0,255,255,255,255,255,255,255,255,255,255,255,255,0,
           0,255,255,255,255,255,255,255,255,255,255,255,255,0,
           0,255,255,255,255,255,255,255,255,255,255,255,255,0])
# BITMAP: width: 43, height: 15
widthBox = bytearray([0,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,254,0,
           0,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,63,0])
# BITMAP: width: 14, height: 15
crossBox = bytearray([0,252,250,246,238,222,190,126,254,254,254,254,254,0,
            0,31,31,31,31,31,31,31,30,29,27,23,15,0])
# BITMAP: width: 12, height: 5
negaBoxWid = bytearray([0,0,0,0,0,0,0,0,0,0,0,0])
# BITMAP: width: 5, height: 12
negaBoxHei = bytearray([0,0,0,0,0,0,0,0,0,0])
negaBoxHeiSprite = thumby.Sprite(5, 12, negaBoxHei)
# BITMAP: width: 3, height: 3
#1-10
hintList = [bytearray([6,7,7]), bytearray([6,6,7]), bytearray([6,6,6]), bytearray([6,6,4]), bytearray([6,4,4]),bytearray([4,4,4]),bytearray([0,4,4]),bytearray([0,0,4]),bytearray([0,0,0]),bytearray([1,0,0]),bytearray([0,1,0]),bytearray([0,0,1]),bytearray([2,0,0]),bytearray([0,2,0]),bytearray([0,0,2]),bytearray([4,0,0]),bytearray([0,4,0]),bytearray([0,0,4])]
hintListNega = [bytearray([1,0,0]),bytearray([1,1,0]),bytearray([1,1,1]),bytearray([1,1,3]),bytearray([1,3,3]),bytearray([3,3,3]),bytearray([7,3,3]),bytearray([7,7,3]),bytearray([7,7,7]),bytearray([6,7,7]),bytearray([7,6,7]),bytearray([7,7,6]),bytearray([5,7,7]),bytearray([7,5,7]),bytearray([7,7,5]),bytearray([3,7,7]),bytearray([7,3,7]),bytearray([7,7,3])]
hintSprites = [thumby.Sprite(3, 3, hintList[i]) for i in range(len(hintList)) ]
hintSpritesNega = [thumby.Sprite(3, 3, hintListNega[i]) for i in range(len(hintListNega)) ]
# BITMAP: width: 5, height: 5から
empBox = bytearray([0,14,14,14,0])
# BITMAP: width: 5, height: 5ばってん 5-9-13-17-21...
banBox = [0,12,10,6]
banBoxes = [ bytearray([banBox[j%4] for j in range(i*4)]+[0]) for i in range(1,10+1)]
# BITMAP: width: 5, height: 5くろぬり
holeBoxes = [ bytearray([ 0 for j in range(i*4+1)]) for i in range(1,10+1)]
# BITMAP: width: 5, height: 5
selectedEmpBox = bytearray([31,31,31,31,31])
# BITMAP: width: 5, height: 5
selectedBanBox = bytearray([31,29,27,23,31])
# BITMAP: width: 5, height: 5
selectedHoleBox = bytearray([31,17,17,17,31])
# BITMAP: width: 72, height: 20
blackBlock = bytearray([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
            0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
            0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
blackBlockSprite = thumby.Sprite(72,20,blackBlock)
clearCheck = False#クリアしたかどうかのフラグ
endCheck = False#クリア後、幕引きのフラグ
thumby.display.setFont("/lib/font3x5.bin", 3, 5, 1)
class Answer(object):#superするからobject継承
    def __init__(self,ans):
        self.ans,self.name = ans#答え
        self.anslen = int(len(self.ans))#答えの長さ(よく使うから)
        self.bace=90#クリア時の画面遷移時間
    def get_line_num(self,issides):#issidesで縦と横の数字列を判断する。0:縦,1:横
        lines=[]
        for i in range(self.anslen):
            line=[]
            linenum=0
            for j in range(self.anslen):
                isopen=None
                if(issides):
                    isopen=self.ans[i][j]#横時
                else:
                    isopen=self.ans[j][i]#縦時
                if isopen:
                    linenum+=1#1なら加算
                else:
                    if(linenum!=0):#linenumを追加
                        line.append(linenum)
                        linenum=0
            if linenum!=0:#最後のlinenumを追加
                line.append(linenum)
                linenum=0
            if(not line):#lineリストが0だったら(軸に穴開けるマスがなかったら)0を入れる
                line.append(0)
            lines.append(line)
        return lines
class AnswerBox:
    #ansの1は埋める穴、0は埋めない穴
    #5x5
    ans1=((1,1,1,1,1),(1,0,1,0,1),(1,1,1,1,1),(1,0,0,0,1),(1,1,1,1,1))
    name1="ROBOT"
    #10x10
    ans2=((0,0,0,0,1,1,1,1,1,1),(0,0,0,0,0,0,0,1,0,0),(0,0,0,0,0,0,1,1,0,0),(0,0,0,0,1,1,0,1,0,0),(0,1,1,1,0,0,0,1,0,0),(1,0,1,1,1,0,1,1,1,0),(1,1,1,1,1,1,0,1,1,1),(1,1,1,1,1,1,1,1,1,1),(0,1,1,1,0,1,1,1,1,1),(0,0,0,0,0,0,1,1,1,0))
    name2="CHERRY"
    ans3=((0,0,1,1,1,0,0,0,0,0),(0,1,1,1,1,1,0,0,0,0),(1,1,0,1,1,1,1,0,0,0),(0,1,1,1,1,1,1,1,1,1),(0,1,1,1,1,1,1,1,0,1),(0,1,1,1,1,1,1,1,0,1),(0,0,1,1,1,1,0,0,1,0),(0,0,0,1,1,1,1,1,0,0),(0,0,0,0,0,1,0,0,0,0),(0,0,0,0,1,1,0,0,0,0))
    name3="HIYOKO"
    def __init__(self, num):
        if(num==0):#いーじー
            self.ans=self.ans1
            self.name=self.name1
        elif(num==1):#のまる
            self.ans=self.ans2
            self.name=self.name2
        else:#はーど
            self.ans=self.ans3
            self.name=self.name3
    def get_answer(self):
        return (self.ans,self.name)
class AnswerIn(Answer):
    def __init__(self, ans):
        super().__init__(ans)
        self.rectsize = math.ceil(500/self.anslen)#四角形の長さ
        self.spacesize = math.ceil(self.rectsize/30)#四角形のスペースの長さ
        self.rectspace = self.rectsize+self.spacesize#四角形+右側スペースまで含めた長さ
        self.texmax = math.ceil(self.anslen/2)#最大のヒント数字の数
        self.setnum = self.anslen#四角形が縦横に何マス必要か(通常ブロック)
    def boolistset(self,num):#正方形の負リストを作る、☓配列、穴配列用
        list=[[False for i in range(num)] for j in range(num)]
        return list
class BlockMake(AnswerIn):#10x10のピクロスブロックを起点にしてマスを作っていく。ピクロスなので5刻みついでにヒントナンバーも作っちゃおうか
    def __init__(self,ans):
        super().__init__(ans)
    #@micropython.viper
    def blockmake(self, pos : int, holelist, banlist):
        if endCheck:
            setX = self.setnum
            setY = self.setnum
            con = (14,0)
            pos = 0
        else:
            setX = self.setnum if self.setnum < 10 else 10
            setY = self.setnum if self.setnum < 6 else 6
            con = (14,15)
            pos = pos
        for y in range(setY):
            boxLen = 0
            isBan = False
            for x in range(setX):
                if not endCheck and banlist[y+pos][x]:
                    if isBan:
                        boxLen += 1
                    else:
                        if boxLen != 0:
                            self.boxspritemaker(isBan,boxLen, x, y, con)
                        boxLen = 1
                        isBan = True
                elif holelist[y+pos][x]:
                    if not isBan:
                        boxLen += 1
                    else:
                        if boxLen != 0:
                            self.boxspritemaker(isBan,boxLen,x, y, con)
                        boxLen = 1
                        isBan = False
                else:#empty
                    if boxLen is not 0:
                        self.boxspritemaker(isBan, boxLen, x, y, con)
                        boxLen = 0
            else:
                if boxLen is not 0:
                    self.boxspritemaker(isBan, boxLen ,setX, y, con)
    def boxspritemaker(self, isBan, boxLen, x, y, con):
        if isBan:
            box = banBoxes[boxLen-1]
        else:
            box = holeBoxes[boxLen-1]
        boxSprite = thumby.Sprite(boxLen*4+1,5,box)
        boxSprite.x = con[0] + (x-boxLen) * 4
        boxSprite.y = con[1] + y * 4
        thumby.display.drawSprite(boxSprite)
    #@micropython.viper
    def textmake(self, pos : int, targetCie):#ヒントマスの数字
        if not endCheck:#クリアしてるなら消失
            ansX = self.anslen if self.anslen < 10 else 10
            ansY = self.anslen if self.anslen < 6 else 6
            altlen = self.get_line_num(True)#横縦
            altlen2 = self.get_line_num(False)#縦横
            for x in range(ansX):
                for i in range(len(altlen2[x])):
                    con = (15,2)
                    hintSprite = hintSprites[altlen2[x][i]-1]
                    hintSprite.x = con[0] + x*4
                    hintSprite.y = con[1] + i*4
                    thumby.display.drawSprite(hintSprite)
            for y in range(ansY):
                for i in range(len(altlen[y+pos])):
                    con = (2,16)
                    hintSprite2 = hintSprites[altlen[y+pos][i]-1]
                    hintSprite2.x = con[0] + i*4
                    hintSprite2.y = con[1] + y*4# - pos * 4
                    thumby.display.drawSprite(hintSprite2)
                    #ヒントマスの中心に来るように
        else:
            for i in range(len(self.name)):
                thumby.display.drawText(self.name[i], 3, i*6+1, 0)
    def gameend(self, endF):
        print(endF)
        blackBlockSprite.x = 0
        blockTop = blackBlockSprite
        blockBtm = blackBlockSprite
        if endF >= 1 and endF <= 30:
            if endF >= 20:
                endF = 20
            
            blockTop.y = -20 + endF
            thumby.display.drawSprite(blockTop)
            blockBtm.y = 40 - endF
            thumby.display.drawSprite(blockBtm)
        elif endF <= 60:
            global endCheck
            endCheck = True
            blockTop.y = 0 - (endF - 31)
            thumby.display.drawSprite(blockTop)
            blockBtm.y = 20 + (endF - 31)
            thumby.display.drawSprite(blockBtm)
class TargetControl(AnswerIn):
    def __init__(self, ans):
        super().__init__(ans)
        self.x,self.y=(0,0)
        self.scrollY=0
    def targetsetter(self, holelist, banlist):
        if banlist[self.y][self.x]:
            box = selectedBanBox
        elif holelist[self.y][self.x]:
            box = selectedHoleBox
        else:
            box = selectedEmpBox
        con = (14,15)#初期位置のx,y
        selectedBoxSprite = thumby.Sprite(5,5,box)
        selectedBoxSprite.x = con[0] + self.x * 4
        selectedBoxSprite.y = con[1] + self.y * 4 - self.scrollY * 4
        thumby.display.drawSprite(selectedBoxSprite)
    def add_x(self):
        if self.x+1<self.anslen:
            self.x+=1
        else:
            self.x=0
    def sub_x(self):
        if self.x==0:
            self.x=self.anslen-1
        else:
            self.x-=1
    def add_y(self):
        if self.y+1<self.anslen:
            self.y+=1
            if self.y-(5+self.scrollY)>0:
                self.scrollY+=1
        else:
            self.y=0
            self.scrollY=0
    def sub_y(self):
        if self.y==0:
            self.y=self.anslen-1
            self.scrollY = self.anslen-6
        else:
            self.y-=1
            if self.scrollY-1==self.y:
                self.scrollY-=1
        
    def get_position(self):
        return self.x,self.y
    def get_scrollY(self):
        return self.scrollY

class TargetReferencer(TargetControl):
    def __init__(self, ans):
        super().__init__(ans)
        self.fc=False,0#移動量調整とその方向調整
        self.delay=0#遅延量
        self.bcs=[False,False]#長押し時、最初の反映Boolでしか上書きしないように
    def movetarget(self):
        if not clearCheck:#クリアしてるなら不可
            time = 0 if self.fc[0] else 1#最初に押したとき遅延が増加
            lrm=(thumby.buttonL.pressed(),thumby.buttonR.pressed(),thumby.buttonU.pressed(),thumby.buttonD.pressed())#移動ボタンの集合
            if not self.delay:#遅延時は操作不能
                if lrm.count(True) == 1:#1個しか押してないこと(斜め移動はできるけどいらん)
                    if thumby.buttonL.pressed():
                        self.sub_x()#xをへらす
                        self.fc=self.fc[1]==1,1#fc調整
                    if thumby.buttonR.pressed():
                        self.add_x()#xを増やす
                        self.fc=self.fc[1]==1,1#fc調整
                    if thumby.buttonU.pressed():
                        self.sub_y()#yを減らす
                        self.fc=self.fc[1]==2,2#fc調整
                    if thumby.buttonD.pressed():
                        self.add_y()#yを増やす
                        self.fc=self.fc[1]==2,2#fc調整
                    if not thumby.buttonA.pressed() and not thumby.buttonB.pressed():
                        thumby.audio.playBlocking(150, 1)
                    if True in lrm:#移動ボタンが押されたときに
                        self.delay=time#遅延を加算
                    else:
                        self.fc=False,0#fc調整
                    
                else:
                    self.fc=False,0#fc調整

            else:
                if True not in lrm:#移動ボタンが押されたときに
                    self.fc=False,0
                self.delay-=1
    def hittarget(self, mainlist, sublist, isrean):#横式なのでyx
        isupg = not (isrean and sublist[self.y][self.x]) and (self.bcs[0] and mainlist[self.y][self.x]!=self.bcs[1] or not self.bcs[0])#上書きするかどうか
        if isupg:#上書き可のときかsublistがFalseのとき
            #music=Music()
            #music.breakbutton()
            if self.bcs[0]:#長押しですでに反映されたBoolにする
                mainlist[self.y][self.x]=self.bcs[1]
            else:
                mainlist[self.y][self.x]=not mainlist[self.y][self.x]#その他は反転
                self.bcs=True,mainlist[self.y][self.x]#最初に押したのを保存しとく
            sublist[self.y][self.x]=False#サブリスト上書き
        return mainlist,sublist
    def clearsetter(self,holelist):#クリア確認、クリア遷移時間の生成
        global clearCheck
        #clearCheck = True
        for holes, anss in zip(holelist, self.ans):
            if holes != list(anss):#一つでも正解と違うなら0を返す
                return
        clearCheck = True
    def brockreplacer(self, holelist, banlist):
        if not clearCheck:
            if thumby.buttonA.pressed():#Aを押したとき
                rean=False
                holelist,banlist=self.hittarget(holelist, banlist, not rean)#C押してるとBanlistのTrueを上書きする(普段はしない)
                thumby.audio.playBlocking(600, 1)
            elif thumby.buttonB.pressed():#Bを押したとき
                rean=False
                banlist,holelist=self.hittarget(banlist, holelist, rean)#C押してるとHolelistのTrueを上書きしない(普段はする)
                thumby.audio.playBlocking(300, 1)
            elif thumby.buttonA.pressed() and thumby.buttonB.pressed():
                banlist,holelist=self.boolistset(self.anslen),self.boolistset(self.anslen)#盤面リセット
                self.bcs=False,False#Bcsもりセット
            else:
                self.bcs=False,False#何も押してなかったらリセッツ
                return holelist, banlist
            self.clearsetter(holelist)
        return holelist, banlist
class Game:
    def game(self, difficult):
        #music=Music()#音楽系
        #music.playnow()
        global clearCheck, endCheck
        clearCheck,endCheck = False,False
        answerbox=AnswerBox(difficult)#0:easy1:normal:2:hard
        answers=answerbox.get_answer()#答え+色+名前
        make=BlockMake(answers)#ブロック表示系の関数
        tr=TargetReferencer(answers)#ターゲット操作系の関数
        holelist=tr.boolistset(len(answers[0]))#どこに穴開けたか
        banlist=tr.boolistset(len(answers[0]))#どこ禁止にしたか
        heightBoxSprite = thumby.Sprite(14, 40, heightBox)
        heightBoxSprite.x = 0
        heightBoxSprite.y = 0
        widthBoxSprite = thumby.Sprite(43, 15, widthBox)
        widthBoxSprite.x = 13
        widthBoxSprite.y = 0
        crossBoxSprite = thumby.Sprite(14, 15, crossBox)
        crossBoxSprite.x = 0
        crossBoxSprite.y = 0
        puzzleVisualSprite = thumby.Sprite(72, 40, puzzleVisual)
        puzzleVisualSprite.x = 0
        puzzleVisualSprite.y = 0
        endF = 0
        while True:
            #デュエル開始
            if not endCheck:
                thumby.display.drawSprite(puzzleVisualSprite)#パズルのヴィジュアルを作成
            else:
                thumby.display.fill(1)
            make.blockmake(tr.get_scrollY(), holelist,banlist)#ブロックを作成
            holelist,banlist=tr.brockreplacer(holelist,banlist)#クリック操作を反映
            make.textmake(tr.get_scrollY(), tr.get_position())#ヒントテキスト
            if not clearCheck:
                tr.targetsetter(holelist, banlist)#ターゲットの作成
                tr.movetarget()#ターゲットの移動
                thumby.display.drawSprite(crossBoxSprite)
            else:
                endF+=1
                make.gameend(endF)
                
            #if checks[0] == make.bace+1:#クリアしたらクリアミュージック発ドン
            #    music.stop()
            #    music.clear()
            #if checks[3] == make.bace+1:#クリア画面遷移が終わったらミュージックがフェードアウト
            #    music.fadeout(make.bace)
            #if checks[3] == 1:#フェードアウトが終わったらゲームを終えタイトル画面へ
            #    break
            
            
            thumby.display.update()

#title=Title()
game=Game()

while True:#メインループ
    #difficult=title.title()#難易度設定
    difficult = 2
    game.game(difficult)#デュエル開始









