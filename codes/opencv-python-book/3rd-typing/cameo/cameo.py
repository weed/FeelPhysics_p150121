# coding=utf-8
__author__ = 'weed'

import cv2
from datetime import datetime
import numpy
import math

import filters
from managers import WindowManager, CaptureManager

class Cameo(object):

    # TODO: 不要になったオプションは廃止する
    ADJUSTING_OPTIONS = (
        HUE_MIN,
        HUE_MAX,
        VALUE_MIN,
        VALUE_MAX,
        SHOULD_PROCESS_GAUSSIAN_BLUR,
        GAUSSIAN_BLUR_KERNEL_SIZE,
        SHOULD_PROCESS_CLOSING,
        CLOSING_ITERATIONS,
        SHOULD_FIND_CIRCLE,
        HOUGH_CIRCLE_RESOLUTION,
        HOUGH_CIRCLE_CANNY_THRESHOLD,
        HOUGH_CIRCLE_ACCUMULATOR_THRESHOLD,
        SHOULD_TRACK_CIRCLE,
        SHOULD_DRAW_CIRCLE,
        SHOULD_DRAW_TRACKS,
        SHOULD_DRAW_VEROCITY_VECTOR,
        SHOULD_DRAW_ACCELERATION_VECTOR,
        SHOWING_FRAME
    ) = range(0, 18)

    SHOWING_FRAME_OPTIONS = (
        ORIGINAL,
        GRAY_SCALE,
        WHAT_COMPUTER_SEE
    ) = range(0, 3)

    def __init__(self):

        self._windowManager = WindowManager('Cameo',
                                            self.onKeypress)
        """:type : managers.WindowManager"""
        # def __init__(self, windowName, keypressCallback = None):

        self._captureManager = CaptureManager(
            cv2.VideoCapture(0), self._windowManager, False)
        """:type : managers.CaptureManager"""
        # def __init__(self, capture, previewWindowManager = None,
        #     shouldMirrorPreview = False):

        ### Filtering
        self._shouldMaskByHue              = False
        self._hueMin                       = 50  # 硬式テニスボール
        self._hueMax                       = 80
        self._valueMin                     = 60
        self._valueMax                     = 260
        self._sThreshold                   = 5
        self._gamma                        = 100
        self._shouldProcessGaussianBlur    = True
        self._gaussianBlurKernelSize       = 20
        self._shouldProcessClosing         = True
        self._closingIterations            = 2

        self._timeSelfTimerStarted         = None

        ### Ball Tracking ###
        self._shouldFindCircle             = False
        self._houghCircleDp                = 4
        self._houghCircleParam1            = 100
        self._houghCircleParam2            = 150
        self._centerPointOfCircle          = None
        self._passedPoints                 = []
        self._shouldDrawCircle             = False
        self._shouldDrawTracks             = False
        self._shouldDrawVerocityVector     = False
        self._lengthTimesOfVerocityVector  = 3
        self._shouldDrawAccelerationVector = False

        self._shouldTrackCircle            = False

        self._currentAdjusting             = self.SHOULD_TRACK_CIRCLE
        self._currentShowing               = self.ORIGINAL

    def _takeScreenShot(self):
        self._captureManager.writeImage(
            datetime.now().strftime('%y%m%d-%H%M%S')
            + '-screenshot.png')
        print 'captured'

    def run(self):
        """
        メインループを実行する
        :return:
        """
        # ウィンドウをつくる
        self._windowManager.createWindow()
        # ウィンドウが存在する限り・・・
        while self._windowManager.isWindowCreated:
            # フレームを取得し・・・
            self._captureManager.enterFrame()
            frameToDisplay = self._captureManager.frame
            frameToFindCircle = frameToDisplay.copy()  # 検出用のフレーム（ディープコピー）

            ### 画面表示

            def _getMaskToFindCircle(self, frame):
                """
                後で円を検出するために、検出用フレームに対して色相フィルタやぼかしなどの処理をする。
                SHOWING_WHAT_COMPUTER_SEEのときは、表示用フレームに対しても同じ処理をする。
                """
                mask = filters.getMaskByHsv(frame, self._hueMin, self._hueMax, self._valueMin, self._valueMax,
                                            self._gamma, self._sThreshold, self._shouldProcessGaussianBlur,
                                            self._gaussianBlurKernelSize, self._shouldProcessClosing,
                                            self._closingIterations)
                return mask

            if self._currentShowing == self.GRAY_SCALE:
                mask = _getMaskToFindCircle(self, frameToDisplay)

                # カメラ画像をHSVチャンネルに分離し・・・
                frame = cv2.cvtColor(frameToDisplay, cv2.COLOR_BGR2HSV)
                h, s, v = cv2.split(frame)

                # マスク部分の明度をガンマ補正し・・・
                v = filters.letMaskMoreBright(v, mask, self._gamma)

                # マスク部分以外は・・・

                # mask（1チャンネル画像）の該当ピクセルが0のとき、
                # notMask（1チャンネル画像）の該当ピクセルを255にセットする。
                # さもなくば、0にセットする。
                # 要するにnotMaskはmaskを反転させたもの。
                notMask = cv2.compare(mask, 0, cv2.CMP_EQ)

                # 彩度を0にする
                cv2.bitwise_and(s, 0, s, notMask) # 論理積

                frame = cv2.merge((h, s, v))
                cv2.cvtColor(frame, cv2.COLOR_HSV2BGR, frameToDisplay)

            elif self._currentShowing == self.WHAT_COMPUTER_SEE:
                gray = _getMaskToFindCircle(self, frameToDisplay)
                cv2.merge((gray, gray, gray), frameToDisplay)

            # elif self._currentShowing == self.ORIGINAL:

            ### 検出・描画処理

            if self._shouldFindCircle:
                frameToFindCircle = _getMaskToFindCircle(self, frameToFindCircle)
                height, width = frameToFindCircle.shape

                # Hough変換で円を検出する
                circles = cv2.HoughCircles(
                    frameToFindCircle,        # 画像
                    cv2.cv.CV_HOUGH_GRADIENT, # アルゴリズムの指定
                    self._houghCircleDp,      # 内部でアキュムレーションに使う画像の分解能(入力画像の解像度に対する逆比)
                    width / 10,               # 円同士の間の最小距離
                    self._houghCircleParam1,  # 内部のエッジ検出(Canny)で使う閾値
                    self._houghCircleParam2,  # 内部のアキュムレーション処理で使う閾値
                    100,                      # 円の最小半径
                    1)                        # 円の最大半径

                # cv2.HoughCircles(image, method, dp, minDist[, circles[, param1[, param2[,
                #                  minRadius[, maxRadius]]]]]) → circles
                # ハフ変換を用いて，グレースケール画像から円を検出します．
                # パラメタ:
                # image – 8ビット，シングルチャンネル，グレースケールの入力画像．
                # circles – 検出された円を出力するベクトル．
                #   各ベクトルは，3要素の浮動小数点型ベクトル  (x, y, radius) としてエンコードされます．
                # method – 現在のところ， CV_HOUGH_GRADIENT メソッドのみが実装されています．
                #   基本的には 2段階ハフ変換 で，これについては Yuen90 で述べられています．
                # dp – 画像分解能に対する投票分解能の比率の逆数．
                #   例えば， dp=1 の場合は，投票空間は入力画像と同じ分解能をもちます．
                #   また dp=2 の場合は，投票空間の幅と高さは半分になります．
                # minDist – 検出される円の中心同士の最小距離．
                #   このパラメータが小さすぎると，正しい円の周辺に別の円が複数誤って検出されることになります．
                #   逆に大きすぎると，検出できない円がでてくる可能性があります．
                # param1 – 手法依存の 1 番目のパラメータ．
                #   CV_HOUGH_GRADIENT の場合は，
                #   Canny() エッジ検出器に渡される2つの閾値の内，大きい方の閾値を表します
                #   （小さい閾値は，この値の半分になります）．
                # param2 – 手法依存の 2 番目のパラメータ．
                #   CV_HOUGH_GRADIENT の場合は，円の中心を検出する際の投票数の閾値を表します．
                #   これが小さくなるほど，より多くの誤検出が起こる可能性があります．
                #   より多くの投票を獲得した円が，最初に出力されます．
                # minRadius – 円の半径の最小値．
                # maxRadius – 円の半径の最大値．

                # もし円を見つけたら・・・
                if circles is not None:
                    # 中心座標と半径を取得して・・・
                    x, y, r = circles[0][0]
                    self._centerPointOfCircle = (x,y)

                    # 円を描く
                    if self._shouldDrawCircle:
                        cv2.circle(frameToDisplay, self._centerPointOfCircle, r, (0,255,0), 5)

                # 次の円を検出したら・・・
                if self._centerPointOfCircle is not None:
                    # 通過点リストの最後に要素を追加する
                    self._passedPoints.append(self._centerPointOfCircle)
                    # self._passedPoints.pop(0)  # 最初の要素は削除する

                # 次の円が見つかっても見つからなくても・・・
                if len(self._passedPoints) != 0:
                    numberOfPoints = len(self._passedPoints)

                    # 軌跡を描画する
                    if self._shouldDrawTracks:
                        if numberOfPoints > 1:
                            for i in range(numberOfPoints - 1):
                                cv2.line(frameToDisplay, self._passedPoints[i],
                                         self._passedPoints[i+1], (0,255,0), 5)

                    def getVerocityVector(passedPoints, lengthTimesOfVerocityVector=3, index=0):
                        # 最後から1個前の点 pt0
                        pt0np = numpy.array(passedPoints[-(2 + index)])
                        # 最後の点 pt1
                        pt1np = numpy.array(passedPoints[-(1 + index)])
                        # 移動ベクトル Δpt = pt1 - pt0
                        dptnp = lengthTimesOfVerocityVector * (pt1np - pt0np)
                        # 移動してなければNoneを返す
                        areSamePoint_array = (dptnp == numpy.array([0,0]))
                        if areSamePoint_array.all():
                            return None
                        else:
                            vector = tuple(dptnp)
                            return vector

                    def cvArrow(img, pt1, pt2, color, thickness=1, lineType=8, shift=0):
                        cv2.line(img,pt1,pt2,color,thickness,lineType,shift)
                        vx = pt2[0] - pt1[0]
                        vy = pt2[1] - pt1[1]
                        v  = math.sqrt(vx ** 2 + vy ** 2)
                        ux = vx / v
                        uy = vy / v
                        # 矢印の幅の部分
                        w = 5
                        h = 10
                        ptl = (int(pt2[0] - uy*w - ux*h), int(pt2[1] + ux*w - uy*h))
                        ptr = (int(pt2[0] + uy*w - ux*h), int(pt2[1] - ux*w - uy*h))
                        # 矢印の先端を描画する
                        cv2.line(img,pt2,ptl,color,thickness,lineType,shift)
                        cv2.line(img,pt2,ptr,color,thickness,lineType,shift)

                    # 速度ベクトルを描画する
                    if self._shouldDrawVerocityVector \
                        and numberOfPoints >= 2 \
                        and self._passedPoints[-1] is not None \
                        and self._passedPoints[-2] is not None:

                        vector = getVerocityVector(self._passedPoints, self._lengthTimesOfVerocityVector)
                        if vector is not None:
                            pt1 = self._passedPoints[-1]
                            pt2 = (pt1[0]+vector[0], pt1[1]+vector[1])

                            cvArrow(frameToDisplay, pt1, pt2, (255,0,0), 5)

                    # 加速度ベクトルを描画する
                    if self._shouldDrawAccelerationVector \
                        and numberOfPoints >= 3 \
                        and self._passedPoints[-1] is not None \
                        and self._passedPoints[-2] is not None \
                        and self._passedPoints[-3] is not None:

                        verocity0 = getVerocityVector(self._passedPoints, self._lengthTimesOfVerocityVector, 1)
                        verocity1 = getVerocityVector(self._passedPoints, self._lengthTimesOfVerocityVector)
                        if verocity0 is not None and verocity1 is not None:
                            v0np = numpy.array(verocity0)
                            v1np = numpy.array(verocity1)
                            dvnp = v1np - v0np  # v1 - v0 = Δv
                            # 速度変化してなければNoneを返す
                            areSamePoint_array = (dvnp == numpy.array([0,0]))
                            if not areSamePoint_array.all():
                                vector = tuple(dvnp)
                                pt1 = self._passedPoints[-1]
                                pt2 = (pt1[0]+vector[0], pt1[1]+vector[1])
                                cvArrow(frameToDisplay, pt1, pt2, (0,0,255), 5)

            ### 情報表示

            # 情報を表示する
            def _putText(text, lineNumber):
                cv2.putText(frameToDisplay, text, (100, 50 + 50 * lineNumber),
                            cv2.FONT_HERSHEY_PLAIN, 2.0, (255,255,255), 3)
            def _put(label, value):
                _putText(label, 1)
                if value is True:
                    value = 'True'
                elif value is False:
                    value = 'False'
                _putText(str(value), 2)

            if   self._currentAdjusting == self.HUE_MIN:
                _put('Hue Min'                            , self._hueMin)
            elif self._currentAdjusting == self.HUE_MAX:
                _put('Hue Max'                            , self._hueMax)
            elif self._currentAdjusting == self.VALUE_MIN:
                _put('Value Min'                          , self._valueMin)
            elif self._currentAdjusting == self.VALUE_MAX:
                _put('Value Max'                          , self._valueMax)
            elif self._currentAdjusting == self.HOUGH_CIRCLE_RESOLUTION:
                _put('Hough Circle Resolution'            , self._houghCircleDp)
            elif self._currentAdjusting == self.HOUGH_CIRCLE_CANNY_THRESHOLD:
                _put('Hough Circle Canny Threshold'       , self._houghCircleParam1)
            elif self._currentAdjusting == self.HOUGH_CIRCLE_ACCUMULATOR_THRESHOLD:
                _put('Hough Circle Accumulator Threshold' , self._houghCircleParam2)
            elif self._currentAdjusting == self.GAUSSIAN_BLUR_KERNEL_SIZE:
                _put('Gaussian Blur Kernel Size'          , self._gaussianBlurKernelSize)
            elif self._currentAdjusting == self.SHOULD_PROCESS_GAUSSIAN_BLUR:
                _put('Process Gaussian Blur'              , self._shouldProcessGaussianBlur)
            elif self._currentAdjusting == self.SHOULD_PROCESS_CLOSING:
                _put('Process Closing'                    , self._shouldProcessClosing)
            elif self._currentAdjusting == self.CLOSING_ITERATIONS:
                _put('Closing Iterations'                 , self._closingIterations)
            elif self._currentAdjusting == self.SHOULD_DRAW_CIRCLE:
                _put('Draw Circle'                        , self._shouldDrawCircle)
            elif self._currentAdjusting == self.SHOULD_DRAW_TRACKS:
                _put('Draw Tracks'                        , self._shouldDrawTracks)
            elif self._currentAdjusting == self.SHOULD_DRAW_VEROCITY_VECTOR:
                _put('Draw Verocity Vector'               , self._shouldDrawVerocityVector)
            elif self._currentAdjusting == self.SHOULD_DRAW_ACCELERATION_VECTOR:
                _put('Draw Acceleration Vector'           , self._shouldDrawAccelerationVector)
            elif self._currentAdjusting == self.SHOULD_FIND_CIRCLE:
                _put('Should Find Circle'                 , self._shouldFindCircle)
            elif self._currentAdjusting == self.SHOULD_TRACK_CIRCLE:
                _put('Should Track Circle'                , self._shouldTrackCircle)
            elif self._currentAdjusting == self.SHOWING_FRAME:
                if   self._currentShowing == self.ORIGINAL:
                    currentShowing = 'Original'
                elif self._currentShowing == self.GRAY_SCALE:
                    currentShowing = 'Gray Scale'
                elif self._currentShowing == self.WHAT_COMPUTER_SEE:
                    currentShowing = 'What Computer See'
                else:
                    raise ValueError('self._currentShowing')

                _put('Showing Frame'                , currentShowing)
            else:
                raise ValueError('self._currentAdjusting')

            # フレームを解放する
            self._captureManager.exitFrame()
            # キーイベントがあれば実行する
            self._windowManager.processEvents()

            # セルフタイマー処理
            if self._timeSelfTimerStarted is not None:
                timeElapsed = datetime.now() - self._timeSelfTimerStarted
                # 3秒たったら・・・
                if timeElapsed.seconds > 3:
                    self._takeScreenShot()
                    # タイマーをリセットする
                    self._timeSelfTimerStarted = None

    def onKeypress(self, keycode):
        """
        キー入力を処理するe
        スペース　：スクリーンショットを撮る
        タブ　　　：スクリーンキャストの録画を開始／終了する
        エスケープ：終了する
        :param keycode: int
        :return: None
        """

        ### 基本操作
        if keycode == 32:  # スペース
            self._captureManager.paused = \
                not self._captureManager.paused
        elif keycode == 13:  # リターン
            self._takeScreenShot()

        elif keycode == 9: # タブ
            # 動画ファイルに書き出し中でなければ・・・
            if not self._captureManager.isWritingVideo:
                # ファイルに書き出すのを始めて・・・
                self._captureManager.startWritingVideo(
                    datetime.now().strftime('%y%m%d-%H%M%S')
                    + '-screencast.avi')
            # 書き出し中であれば・・・
            else:
                # ・・・書き出しを終える
                self._captureManager.stopWritingVideo()
        elif keycode == 27: # エスケープ
            self._windowManager.destroyWindow()

        ### Hue Filter ###
        elif keycode == ord('B'):
            self._hueMin = 200
            self._hueMax = 240
        elif keycode == ord('G'):
            self._hueMin = 80
            self._hueMax = 200
        elif keycode == ord('R'):
            self._hueMin = 0
            self._hueMax = 20
        elif keycode == ord('Y'):
            self._hueMin = 50
            self._hueMax = 80

        elif keycode == ord('p'):
             self._timeSelfTimerStarted = datetime.now()

        ### Adjustment
        elif keycode == 3:  # right arrow
            if not self._currentAdjusting == len(self.ADJUSTING_OPTIONS) - 1:
                self._currentAdjusting += 1
            else:
                self._currentAdjusting = 0
        elif keycode == 2:  # left arrow
            if not self._currentAdjusting == 0:
                self._currentAdjusting -= 1
            else:
                self._currentAdjusting = len(self.ADJUSTING_OPTIONS) - 1
        elif keycode == 0 or keycode == 1:  # up / down arrow
            if self._currentAdjusting   == self.HUE_MIN:
                pitch = 10 if keycode == 0 else -10
                self._hueMin            += pitch
            elif self._currentAdjusting == self.HUE_MAX:
                pitch = 10 if keycode == 0 else -10
                self._hueMax            += pitch
            elif self._currentAdjusting == self.VALUE_MIN:
                pitch = 10 if keycode == 0 else -10
                self._valueMin          += pitch
            elif self._currentAdjusting == self.VALUE_MAX:
                pitch = 10 if keycode == 0 else -10
                self._valueMax          += pitch
            elif self._currentAdjusting == self.HOUGH_CIRCLE_RESOLUTION:
                pitch = 1  if keycode == 0 else -1
                self._houghCircleDp     += pitch
            elif self._currentAdjusting == self.HOUGH_CIRCLE_CANNY_THRESHOLD:
                pitch = 20 if keycode == 0 else -20
                self._houghCircleParam1 += pitch
            elif self._currentAdjusting == self.HOUGH_CIRCLE_ACCUMULATOR_THRESHOLD:
                pitch = 50 if keycode == 0 else -50
                self._houghCircleParam2 += pitch
            elif self._currentAdjusting == self.GAUSSIAN_BLUR_KERNEL_SIZE:
                pitch = 1  if keycode == 0 else -1
                self._gaussianBlurKernelSize += pitch
            elif self._currentAdjusting == self.SHOULD_PROCESS_GAUSSIAN_BLUR:
                self._shouldProcessGaussianBlur = \
                    not self._shouldProcessGaussianBlur
            elif self._currentAdjusting == self.SHOULD_PROCESS_CLOSING:
                self._shouldProcessClosing = \
                    not self._shouldProcessClosing
            elif self._currentAdjusting == self.CLOSING_ITERATIONS:
                pitch = 1  if keycode == 0 else -1
                self._closingIterations += pitch
            elif self._currentAdjusting == self.SHOULD_DRAW_CIRCLE:
                if  self._shouldDrawCircle:
                    self._shouldDrawCircle = False
                else:
                    self._shouldFindCircle = True
                    self._shouldDrawCircle = True
            elif self._currentAdjusting == self.SHOULD_DRAW_TRACKS:
                if  self._shouldDrawTracks:
                    self._shouldDrawTracks = False
                else:
                    self._shouldFindCircle = True
                    self._passedPoints = []  # 軌跡を消去する
                    self._shouldDrawTracks = True
            elif self._currentAdjusting == self.SHOULD_DRAW_VEROCITY_VECTOR:
                if  self._shouldDrawVerocityVector:
                    self._shouldDrawVerocityVector = False
                else:
                    self._shouldFindCircle = True
                    self._shouldDrawVerocityVector = True
            elif self._currentAdjusting == self.SHOULD_DRAW_ACCELERATION_VECTOR:
                if  self._shouldDrawAccelerationVector:
                    self._shouldDrawAccelerationVector = False
                else:
                    self._shouldFindCircle = True
                    self._shouldDrawAccelerationVector = True
            elif self._currentAdjusting == self.SHOULD_FIND_CIRCLE:
                self._shouldFindCircle = \
                    not self._shouldFindCircle
            elif self._currentAdjusting == self.SHOULD_TRACK_CIRCLE:
                if  self._shouldTrackCircle:
                    self._shouldTrackCircle = False
                else:
                    self._shouldFindCircle  = False
                    self._shouldTrackCircle = True
            elif self._currentAdjusting == self.SHOWING_FRAME:
                if   keycode == 0:  # up arrow
                    if not self._currentShowing == len(self.SHOWING_FRAME_OPTIONS) - 1:
                        self._currentShowing += 1
                    else:
                        self._currentShowing = 0
                elif keycode == 1:  # down arrow
                    if not self._currentShowing == 0:
                        self._currentShowing -= 1
                    else:
                        self._currentShowing = len(self.SHOWING_FRAME_OPTIONS) - 1

            else:
                raise ValueError('self._currentAdjusting')

        else:
            print keycode

if __name__ == "__main__":
    Cameo().run()