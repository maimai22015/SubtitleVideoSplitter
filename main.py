import glob
import re
import os
import datetime
import subprocess
from logging import basicConfig, getLogger, DEBUG

def SelectSubPath():
    """
    字幕・動画音声ファイルの選択

    Returns
    ----------
    SubPathList : list
        字幕ファイルのパスのリスト
    VidPathList : list
        動画音声ファイルのパスのリスト
    """
    logger.info("字幕ファイルを選択 ファイルパスもしくは「*.srt」の形式で拡張子を入力")
    # Note: ファイル名順に処理されます。ファイルのナンバリングが同じ順番になるようにしてください
    inputpath = input("> ")
    SubPathList = []
    if "*." in inputpath:
        files = glob.glob(inputpath)
        SubPathList = files
    elif "" == inputpath:
        logger.critical("字幕ファイルが選択されていません")
        raise(Exception)
    else:
        SubPathList.append(inputpath)
    logger.info("動画・音声ファイルを選択 ファイルパスもしくは「*.mp4」の形式で拡張子を入力")
    inputpath = input("> ")
    VidPathList = []
    if "*." in inputpath:
        files = glob.glob(inputpath)
        VidPathList = files
    elif "" == inputpath:
        logger.critical("動画・音声ファイルが選択されていません")
        raise(Exception)
    else:
        VidPathList.append(inputpath)
    if len(SubPathList) != len(VidPathList):
        raise(Exception)
    return SubPathList, VidPathList


def LoadSrtFile(readlines):
    """
    srtファイルの解析、HTMLタグの除去

    Parameters
    ----------
    readlines : list
        字幕ファイルの中身

    Returns
    ----------
    SubParse : list
        解析済みの字幕ファイルの中身
        ID_00:00:00,000_11:11:11,111_TEXTTEXT
    """
    re_pattern = r'[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}'
    regex = re.compile(re_pattern)
    rehtml = re.compile('<.*?>')
    rehtml2 = re.compile('{.*?}')
    SubParse = []
    for i in range(len(readlines)):
        if regex.match(readlines[i]):
            try:
                SubText = readlines[i+1].rstrip("\n")+readlines[i+2].rstrip("\n") if readlines[i+2] != "\n" else readlines[i+1].rstrip("\n")
            except: # 例外発生時(srtファイル最終行等を想定)
                SubText = readlines[i+1].rstrip("\n")
            # ここでSubTextのhtmlタグ除去の操作を行う
            SubText = re.sub(rehtml, "", SubText)
            SubText = re.sub(rehtml2, "", SubText)
            #                ID                         ,00:00:00,000               ,11:11:11,111                            ,TEXTTEXT
            SubParse.append([readlines[i-1].rstrip("\n"), readlines[i].split(" ")[0], readlines[i].split(" ")[2].rstrip("\n"), SubText])
    return SubParse

def LoadAssFile(readlines):
    """
    assファイルの解析、装飾タグの除去 検証は不十分。

    Parameters
    ----------
    readlines : list
        字幕ファイルの中身

    Returns
    ----------
    SubParse : list
        解析済みの字幕ファイルの中身
        ID_00:00:00,000_11:11:11,111_TEXTTEXT
    """
    SubParse = []
    assid = 1
    rehtml2 = re.compile('{.*?}')
    rehtml3 = re.compile('.*?}')
    for readline in readlines:
        if readline.startswith("Dialogue:"):
            SubText = re.sub(rehtml2, "", readline.split(",")[-1].rstrip("\n"))
            SubText = re.sub(rehtml3, "", SubText) # 装飾{\pos(xxx,xxx)}の処理。
            SubText = re.sub("\u3000", " ", SubText)
            SubParse.append([assid,readline.split(",")[1]+"0",readline.split(",")[2]+"0",SubText])
            assid = assid+1
    return SubParse

def LoadSubtitle(SubPath):
    """
    字幕ファイルのファイル読み込み

    Parameters
    ----------
    SubPath : str
        字幕ファイルのパス

    Returns
    ----------
    SubParse : list
        解析済みの字幕ファイルの中身 Load***Fileの返り値そのまま
        ID_00-00-00,000_11-11-11,111-TEXTTEXT
    """
    with open(SubPath, encoding="utf-8") as f:
        readlines = f.readlines()
    SubExt = SubPath.split(".")[-1]
    if SubExt == "srt":
        SubParse = LoadSrtFile(readlines)
    elif SubExt == "ass" or SubExt == "ssa":
        SubParse = LoadAssFile(readlines)
    return SubParse


def TimeDelta(TimeStart, TimeEnd, TimeOffset="00:00:00.000"):
    """
    時間の計算

    Parameters
    ----------
    TimeStart : str
        時間 00:00:00.000
    TimeEnd : str
        時間変化値 00:00:00.
    TimeOffset : srt
        オフセット

    Returns
    ----------
    TimeStart : datetime -> str
        計算済み開始時間 00:00:00.000
    TimeEnd : dimedelta -> srt
        長さ 00:00:00.000
    """
    TimeStart = datetime.datetime.strptime(TimeStart+"000", '%H:%M:%S.%f')
    TimeEnd = datetime.datetime.strptime(TimeEnd+"000", '%H:%M:%S.%f')
    OffsetMinus = True if TimeOffset[0] == "-" else False
    TimeOffset = datetime.datetime.strptime(
        TimeOffset+"000", '%H:%M:%S.%f') if TimeOffset[0] != "-" else datetime.datetime.strptime(TimeOffset+"000", '-%H:%M:%S.%f')
    TimeOffset = datetime.timedelta(hours=TimeOffset.hour, minutes=TimeOffset.minute,
                                    seconds=TimeOffset.second, microseconds=TimeOffset.microsecond)
    TimeMargin = datetime.timedelta(microseconds=500000)
    if OffsetMinus:
        TimeStart = TimeStart - TimeMargin - TimeOffset if (TimeStart - TimeMargin - TimeOffset).day == 1 else TimeStart
        TimeEnd = TimeEnd + TimeMargin - TimeOffset
        TimeEnd = TimeEnd-TimeStart
    else:
        TimeStart = TimeStart - TimeMargin + TimeOffset if (TimeStart - TimeMargin + TimeOffset).day == 1 else TimeStart + TimeOffset
        TimeEnd = TimeEnd + TimeMargin + TimeOffset
        TimeEnd = TimeEnd-TimeStart
    TimeEnd  = datetime.datetime(1990,1,1,second=TimeEnd.seconds,microsecond=TimeEnd.microseconds)
    return TimeStart.strftime("%H:%M:%S.%f")[:-3],TimeEnd.strftime("%H:%M:%S.%f")[:-3]


def RunFfmpeg(SubPath, VidPath):
    SubList = LoadSubtitle(SubPath)
    try:
        OutPutPath = VidPath.split("\/")[-1].rsplit(".", 1)[0]
        os.mkdir(OutPutPath)
        logger.info("フォルダ作成成功 : '" + OutPutPath + "'")
    except:
        logger.error("フォルダ作成失敗")
        # raise(Exception)
    refile = re.compile(r'[\\|/|:|?|"|<|>|,|.|\|]')
    for SubListItem in SubList:
        ItemStartTime, ItemEndTime = TimeDelta(SubListItem[1].replace(",", "."),SubListItem[2].replace(",", "."))
        OutPutFileName = "_".join([str(n) for n in SubListItem])
        OutPutFileName = re.sub(refile,"-", OutPutFileName)+"."+VidPath.split(".")[-1]
        ffmpegCommand = "ffmpeg -ss {} -i {} -t {} -c copy {}".format(ItemStartTime,'"'+VidPath+'"',ItemEndTime,'"'+OutPutPath+"\\"+OutPutFileName+'"')
        logger.info(ffmpegCommand)
        result = subprocess.run(ffmpegCommand, shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return


if __name__ == "__main__":

    # logging setting
    logger = getLogger(__name__)
    logger.setLevel(DEBUG)
    basicConfig(
        format='[%(asctime)s] %(name)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 字幕・動画ファイルを選択
    SubPathList, VidPathList = SelectSubPath()
    logger.info("事前にffmpegを導入しておく必要があります。")

    for i in range(len(SubPathList)):
        RunFfmpeg(SubPathList[i], VidPathList[i])
