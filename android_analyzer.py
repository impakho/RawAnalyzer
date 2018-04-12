import os, sys
import re
import codecs
import threading
import fcntl
import subprocess
import time
import hashlib
import traceback
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtWebKit import *
from PyQt5.QtWebKitWidgets import *

openFilePath = ""
openFileName = ""
pt_offset = []
pt_sector = []
pt_type = []
pt_name = []
mount_dev = []
mount_path = []
image_format = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'tiff', 'tga']
audio_format = ['mp3', 'wav', 'wmv', 'flac', 'ape', 'aac']
video_format = ['mp4', 'mpg', 'mpeg', 'rm', 'rmvb', 'avi', 'wmv', 'mkv', '3gp', 'mov', 'flv', 'f4v', 'm4v', 'ts', 'mts', 'm2ts', 'vob']
recover_image_format = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'rif']
recover_media_format = ['wav', 'mp4', 'mpg', 'mpeg', 'avi', 'wmv', 'mov']
recover_document_format = ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'pdf']
recover_other_format = ['rar', 'zip', 'htm', 'html', 'exe', 'ole', 'sxc', 'sxi', 'sxw']
map_url = "http://api.map.baidu.com/lbsapi/cloud/jsdemo/demo/a1_2.htm"
map_data = []

def calcLen(length):
    length1 = hex(length[3])[2:]
    length2 = hex(length[2])[2:]
    length3 = hex(length[1])[2:]
    length4 = hex(length[0])[2:]
    if len(length1) == 1: length1 = "0" + length1
    if len(length2) == 1: length2 = "0" + length2
    if len(length3) == 1: length3 = "0" + length3
    if len(length4) == 1: length4 = "0" + length4
    return int(length1+length2+length3+length4,16)

def findMBR(filename,sector,offset):
    fd = open(filename,'rb')
    fd.seek(offset*sector)
    mbr = fd.read(sector)
    fd.close()
    if codecs.encode(mbr[-2:],'hex') != b"55aa": return
    mbr = mbr[-66:]
    for i in range(0,4):
        runDPT(filename,sector,offset,mbr[i*16:(i+1)*16])

def runDPT(filename,sector,offset,dpt):
    flag = codecs.encode(dpt[4:5],'hex')
    if flag == b"00": return
    length = calcLen(dpt[8:12])
    if flag == b"05":
        findEBR(filename,sector,offset+length,offset+length)
        return
    pt_offset.append(offset+length)
    pt_sector.append(calcLen(dpt[12:16]))
    typePT(filename,sector,offset+length)
    namePT(filename,sector,offset+length)

def findEBR(filename,sector,first,offset):
    fd = open(filename,'rb')
    fd.seek(offset*sector)
    ebr = fd.read(sector)
    fd.close()
    if codecs.encode(ebr[-2:],'hex') != b"55aa": return
    ebr = ebr[-66:]
    pt_offset.append(offset+calcLen(ebr[8:12]))
    pt_sector.append(calcLen(ebr[12:16]))
    typePT(filename,sector,offset+calcLen(ebr[8:12]))
    namePT(filename,sector,offset+calcLen(ebr[8:12]))
    if codecs.encode(ebr[20:21],'hex') == b"05":
        findEBR(filename,sector,first,first+calcLen(ebr[24:28]))

def typePT(filename,sector,offset):
    fd = open(filename,'rb')
    fd.seek(offset*sector)
    dbr = fd.read(sector*3)
    fd.close()
    if codecs.encode(dbr[sector*2+56:sector*2+58],'hex') == b"53ef":
        pt_type.append("EXTX")
        return
    if codecs.encode(dbr[sector-2:sector],'hex') == b"55aa":
        if dbr[3:7] == "NTFS":
            pt_type.append("NTFS")
            return
        if dbr[82:87] == "FAT32":
            pt_type.append("FAT32")
            return
        if dbr[54:59] == "FAT16":
            pt_type.append("FAT16")
            return
        if dbr[54:59] == "FAT12":
            pt_type.append("FAT12")
            return
    pt_type.append("Uknown")

def namePT(filename,sector,offset):
    fd = open(filename,'rb')
    fd.seek(offset*sector)
    dbr = fd.read(sector*3)
    fd.close()
    if codecs.encode(dbr[sector*2+56:sector*2+58],'hex') == b"53ef":
        pt_name.append(str(dbr[sector*2+120:sector*2+152].strip(b'\x00').strip(b'\x20'),'ascii'))
        return
    if codecs.encode(dbr[sector-2:sector],'hex') == b"55aa":
        if dbr[3:7] == "NTFS":
            pt_name.append(str(dbr[72:80].strip(b'\x00').strip(b'\x20'),'ascii'))
            return
        if dbr[82:87] == "FAT32":
            pt_name.append(str(dbr[71:82].strip(b'\x00').strip(b'\x20'),'ascii'))
            return
        if dbr[54:59] == "FAT16":
            pt_name.append(str(dbr[43:54].strip(b'\x00').strip(b'\x20'),'ascii'))
            return
        if dbr[54:59] == "FAT12":
            pt_name.append(str(dbr[43:54].strip(b'\x00').strip(b'\x20'),'ascii'))
            return
    pt_name.append("")

def map_getMinMax():
    if len(map_data) <= 0: return
    minLat = 9999
    minLon = 9999
    maxLat = -9999
    maxLon = -9999
    for metadata in map_data:
        if metadata[1] < minLat: minLat = metadata[1]
        if metadata[1] > maxLat: maxLat = metadata[1]
        if metadata[2] < minLon: minLon = metadata[2]
        if metadata[2] > maxLon: maxLon = metadata[2]
    return minLat, maxLat, minLon, maxLon

def map_getCenter():
    if len(map_data) <= 0: return
    minLat, maxLat, minLon, maxLon = map_getMinMax()
    centerLat = (minLat + maxLat) / 2
    centerLon = (minLon + maxLon) / 2
    return centerLat, centerLon

def map_getZoom():
    if len(map_data) <= 0: return
    minLat, maxLat, minLon, maxLon = map_getMinMax()
    zoomLat = (maxLat - minLat) * 111110 / 9
    zoomLon = (maxLon - minLon) * 111110 / 9
    zoom = zoomLat
    if zoomLat < zoomLon: zoom = zoomLon
    if zoom <= 20: return 19
    if zoom <= 50: return 18
    if zoom <= 100: return 17
    if zoom <= 200: return 16
    if zoom <= 500: return 15
    if zoom <= 1000: return 14
    if zoom <= 2000: return 13
    if zoom <= 5000: return 12
    if zoom <= 10000: return 11
    if zoom <= 20000: return 10
    if zoom <= 25000: return 9
    if zoom <= 50000: return 8
    if zoom <= 100000: return 7
    if zoom <= 200000: return 6
    if zoom <= 500000: return 5
    if zoom <= 1000000: return 4
    if zoom <= 2000000: return 3
    if zoom <= 5000000: return 2
    return 1

def map_hideCpy(webView):
    webView.page().mainFrame().evaluateJavaScript("document.getElementsByClassName('BMap_cpyCtrl')[0].style.display = 'none';")
    webView.page().mainFrame().evaluateJavaScript("document.getElementById('zoomer').previousSibling.style.display = 'none';")

class App(QMainWindow):

    def __init__(self):
        super().__init__()
        self.title = 'Android手机取证工具'
        self.left = 150
        self.top = 150
        self.width = 800
        self.height = 500
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.table_widget = MyTableWidget(self)
        self.setCentralWidget(self.table_widget)

        self.show()

    def closeEvent(self, event):
        os._exit(0)

class MyTableWidget(QWidget):

    def __init__(self, parent):
        super(QWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        # Initialize tab screen
        self.tabs = QTabWidget()
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        self.tab4 = QWidget()
        self.tab5 = QWidget()
        self.tab6 = QWidget()
        self.tab7 = QWidget()
        self.tabs.resize(800, 500)

        # Add tabs
        self.tabs.addTab(self.tab1, "镜像文件分析")
        self.tabs.addTab(self.tab2, "文件内容搜索")
        self.tabs.addTab(self.tab3, "特征文件搜索")
        self.tabs.addTab(self.tab4, "相似图片搜索")
        self.tabs.addTab(self.tab5, "文件数据恢复")
        self.tabs.addTab(self.tab6, "GPS轨迹分析")
        self.tabs.addTab(self.tab7, "数据库分析")

        # Tab 1
        self.tab1.layout = QVBoxLayout(self)
        # button_openfile
        self.tab1.button_openfile = QPushButton("分析镜像文件")
        self.tab1.button_openfile.clicked.connect(self.tab1_openfile_click)
        # button_savefile
        self.tab1.button_savefile = QPushButton("保存分区文件")
        self.tab1.button_savefile.clicked.connect(self.tab1_savefile_click)
        # button_repairfile
        self.tab1.button_repairfile = QPushButton("修复分区文件")
        self.tab1.button_repairfile.clicked.connect(self.tab1_repairfile_click)
        # button_mountfile
        self.tab1.button_mountfile = QPushButton("挂载分区文件")
        self.tab1.button_mountfile.clicked.connect(self.tab1_mountfile_click)
        # button_umountdrive
        self.tab1.button_umountdrive = QPushButton("卸载分区")
        self.tab1.button_umountdrive.clicked.connect(self.tab1_umountdrive_click)
        # list_filedetail
        self.tab1.list_filedetail = QListWidget(self)
        # list_mountdetail
        self.tab1.list_mountdetail = QListWidget(self)
        # label_sectoroffset
        self.tab1.label_sectoroffset = QLabel("扇区偏移：")
        # textbox_sectoroffset
        self.tab1.textbox_sectoroffset = QLineEdit("0")
        # label_sectorsize
        self.tab1.label_sectorsize = QLabel("扇区大小：")
        # textbox_sectorsize
        self.tab1.textbox_sectorsize = QLineEdit("512")
        # label_blocksize
        self.tab1.label_blocksize = QLabel("块大小：")
        # textbox_blocksize
        self.tab1.textbox_blocksize = QLineEdit("4096")
        # label_repairfs
        self.tab1.label_repairfs = QLabel("文件系统：")
        # textbox_repairfs
        self.tab1.textbox_repairfs = QLineEdit("ext4")
        # label_mountparams
        self.tab1.label_mountparams = QLabel("挂载参数：")
        # textbox_mountparams
        self.tab1.textbox_mountparams = QLineEdit("-o loop,ro,noexec,noload")
        # button_adb
        self.tab1.button_adb = QPushButton("ADB一键提取数据（需要ROOT）")
        self.tab1.button_adb.clicked.connect(self.tab1_adb_click)
        # Add widgets to tab
        self.tab1.layout1 = QHBoxLayout(self)
        self.tab1.layout2 = QHBoxLayout(self)
        self.tab1.layout3 = QHBoxLayout(self)
        self.tab1.layout4 = QHBoxLayout(self)
        self.tab1.layout5 = QHBoxLayout(self)
        self.tab1.layout6 = QHBoxLayout(self)
        self.tab1.layout1.addWidget(self.tab1.button_openfile)
        self.tab1.layout1.addWidget(self.tab1.button_savefile)
        self.tab1.layout1.addWidget(self.tab1.button_repairfile)
        self.tab1.layout1.addWidget(self.tab1.button_mountfile)
        self.tab1.layout1.addWidget(self.tab1.button_umountdrive)
        self.tab1.layout2.addWidget(self.tab1.list_filedetail)
        self.tab1.layout2.addWidget(self.tab1.list_mountdetail)
        self.tab1.layout3.addWidget(self.tab1.label_sectoroffset)
        self.tab1.layout3.addWidget(self.tab1.textbox_sectoroffset)
        self.tab1.layout3.addWidget(self.tab1.label_sectorsize)
        self.tab1.layout3.addWidget(self.tab1.textbox_sectorsize)
        self.tab1.layout4.addWidget(self.tab1.label_blocksize)
        self.tab1.layout4.addWidget(self.tab1.textbox_blocksize)
        self.tab1.layout4.addWidget(self.tab1.label_repairfs)
        self.tab1.layout4.addWidget(self.tab1.textbox_repairfs)
        self.tab1.layout5.addWidget(self.tab1.label_mountparams)
        self.tab1.layout5.addWidget(self.tab1.textbox_mountparams)
        self.tab1.layout6.addWidget(self.tab1.button_adb)
        self.tab1.layout.addLayout(self.tab1.layout1)
        self.tab1.layout.addLayout(self.tab1.layout2)
        self.tab1.layout.addLayout(self.tab1.layout3)
        self.tab1.layout.addLayout(self.tab1.layout4)
        self.tab1.layout.addLayout(self.tab1.layout5)
        self.tab1.layout.addStretch()
        self.tab1.layout.addLayout(self.tab1.layout6)
        self.tab1.layout.addStretch()
        self.tab1.setLayout(self.tab1.layout)

        # Tab 2
        self.tab2.layout = QVBoxLayout(self)
        # label_searchdir
        self.tab2.label_searchdir = QLabel("搜索目录：")
        # textbox_searchdir
        self.tab2.textbox_searchdir = QLineEdit(self)
        # button_searchdir
        self.tab2.button_searchdir = QPushButton("选择目录")
        self.tab2.button_searchdir.clicked.connect(self.tab2_searchdir_click)
        # label_searchkeyword
        self.tab2.label_searchkeyword = QLabel("关键词：")
        # textbox_search
        self.tab2.textbox_search = QLineEdit(self)
        # label_searchtype
        self.tab2.label_searchtype = QLabel("类型：")
        # buttongroup_searchtype
        self.tab2.buttongroup_searchtype = QButtonGroup(self)
        # radiobutton_string
        self.tab2.radiobutton_string = QRadioButton("字符串")
        self.tab2.radiobutton_string.setChecked(True)
        # radiobutton_hex
        self.tab2.radiobutton_hex = QRadioButton("16进制")
        # button_search
        self.tab2.button_search = QPushButton("搜索")
        self.tab2.button_search.clicked.connect(self.tab2_search_click)
        # label_searchsize
        self.tab2.label_searchsize = QLabel("大小：")
        # buttongroup_searchsize
        self.tab2.buttongroup_searchsize = QButtonGroup(self)
        # radiobutton_sizeoff
        self.tab2.radiobutton_sizeoff = QRadioButton("无限制")
        self.tab2.radiobutton_sizeoff.setChecked(True)
        # radiobutton_sizeon
        self.tab2.radiobutton_sizeon = QRadioButton("自定义")
        # label_sizesm
        self.tab2.label_sizesm = QLabel("大于")
        self.tab2.label_sizesm.setFixedWidth(30)
        # textbox_sizesm
        self.tab2.textbox_sizesm = QLineEdit("0")
        self.tab2.textbox_sizesm.setFixedWidth(60)
        # combobox_sizesm
        self.tab2.combobox_sizesm = QComboBox(self)
        self.tab2.combobox_sizesm.setFixedWidth(80)
        self.tab2.combobox_sizesm.addItem("KB")
        self.tab2.combobox_sizesm.addItem("MB")
        self.tab2.combobox_sizesm.addItem("GB")
        # label_sizebg
        self.tab2.label_sizebg = QLabel("小于")
        self.tab2.label_sizebg.setFixedWidth(30)
        # textbox_sizebg
        self.tab2.textbox_sizebg = QLineEdit("512")
        self.tab2.textbox_sizebg.setFixedWidth(60)
        # combobox_sizebg
        self.tab2.combobox_sizebg = QComboBox(self)
        self.tab2.combobox_sizebg.setFixedWidth(80)
        self.tab2.combobox_sizebg.addItem("KB")
        self.tab2.combobox_sizebg.addItem("MB")
        self.tab2.combobox_sizebg.addItem("GB")
        self.tab2.combobox_sizebg.setCurrentIndex(1)
        # label_searchtime
        self.tab2.label_searchtime = QLabel("修改时间：")
        # buttongroup_searchtime
        self.tab2.buttongroup_searchtime = QButtonGroup(self)
        # radiobutton_timeoff
        self.tab2.radiobutton_timeoff = QRadioButton("无限制")
        self.tab2.radiobutton_timeoff.setChecked(True)
        # radiobutton_timeon
        self.tab2.radiobutton_timeon = QRadioButton("自定义")
        # label_timesm
        self.tab2.label_timesm = QLabel("大于")
        self.tab2.label_timesm.setFixedWidth(30)
        # datetime_timesm
        self.tab2.datetime_timesm = QDateTimeEdit(self)
        self.tab2.datetime_timesm.setCalendarPopup(True)
        self.tab2.datetime_timesm_dt = QDateTime()
        self.tab2.datetime_timesm_dt.setTime_t(time.time() - 1296000)
        self.tab2.datetime_timesm.setDateTime(self.tab2.datetime_timesm_dt)
        # label_timebg
        self.tab2.label_timebg = QLabel("小于")
        self.tab2.label_timebg.setFixedWidth(30)
        # datetime_timebg
        self.tab2.datetime_timebg = QDateTimeEdit(self)
        self.tab2.datetime_timebg.setCalendarPopup(True)
        self.tab2.datetime_timebg_dt = QDateTime()
        self.tab2.datetime_timebg_dt.setTime_t(time.time())
        self.tab2.datetime_timebg.setDateTime(self.tab2.datetime_timebg_dt)
        # label_searchresult
        self.tab2.label_searchresult = QLabel("搜索结果：")
        # list_searchresult
        self.tab2.list_searchresult = QListWidget(self)
        # Add widgets to tab
        self.tab2.layout1 = QHBoxLayout(self)
        self.tab2.layout2 = QHBoxLayout(self)
        self.tab2.layout3 = QHBoxLayout(self)
        self.tab2.layout4 = QHBoxLayout(self)
        self.tab2.layout5 = QHBoxLayout(self)
        self.tab2.layout6 = QHBoxLayout(self)
        self.tab2.layout7 = QHBoxLayout(self)
        self.tab2.layout1.addWidget(self.tab2.label_searchdir)
        self.tab2.layout1.addWidget(self.tab2.textbox_searchdir)
        self.tab2.layout1.addWidget(self.tab2.button_searchdir)
        self.tab2.layout2.addWidget(self.tab2.label_searchkeyword)
        self.tab2.layout2.addWidget(self.tab2.textbox_search)
        self.tab2.layout3.addWidget(self.tab2.label_searchtype)
        self.tab2.buttongroup_searchtype.addButton(self.tab2.radiobutton_string)
        self.tab2.buttongroup_searchtype.addButton(self.tab2.radiobutton_hex)
        self.tab2.layout3.addWidget(self.tab2.radiobutton_string)
        self.tab2.layout3.addWidget(self.tab2.radiobutton_hex)
        self.tab2.layout3.addWidget(self.tab2.button_search)
        self.tab2.layout4.addWidget(self.tab2.label_searchsize)
        self.tab2.buttongroup_searchsize.addButton(self.tab2.radiobutton_sizeoff)
        self.tab2.buttongroup_searchsize.addButton(self.tab2.radiobutton_sizeon)
        self.tab2.layout4.addWidget(self.tab2.radiobutton_sizeoff)
        self.tab2.layout4.addWidget(self.tab2.radiobutton_sizeon)
        self.tab2.layout4.addWidget(self.tab2.label_sizesm)
        self.tab2.layout4.addWidget(self.tab2.textbox_sizesm)
        self.tab2.layout4.addWidget(self.tab2.combobox_sizesm)
        self.tab2.layout4.addWidget(self.tab2.label_sizebg)
        self.tab2.layout4.addWidget(self.tab2.textbox_sizebg)
        self.tab2.layout4.addWidget(self.tab2.combobox_sizebg)
        self.tab2.layout5.addWidget(self.tab2.label_searchtime)
        self.tab2.buttongroup_searchtime.addButton(self.tab2.radiobutton_timeoff)
        self.tab2.buttongroup_searchtime.addButton(self.tab2.radiobutton_timeon)
        self.tab2.layout5.addWidget(self.tab2.radiobutton_timeoff)
        self.tab2.layout5.addWidget(self.tab2.radiobutton_timeon)
        self.tab2.layout5.addWidget(self.tab2.label_timesm)
        self.tab2.layout5.addWidget(self.tab2.datetime_timesm)
        self.tab2.layout5.addWidget(self.tab2.label_timebg)
        self.tab2.layout5.addWidget(self.tab2.datetime_timebg)
        self.tab2.layout6.addWidget(self.tab2.label_searchresult)
        self.tab2.layout7.addWidget(self.tab2.list_searchresult)
        self.tab2.layout.addLayout(self.tab2.layout1)
        self.tab2.layout.addLayout(self.tab2.layout2)
        self.tab2.layout.addLayout(self.tab2.layout3)
        self.tab2.layout.addLayout(self.tab2.layout4)
        self.tab2.layout.addLayout(self.tab2.layout5)
        self.tab2.layout.addStretch()
        self.tab2.layout.addLayout(self.tab2.layout6)
        self.tab2.layout.addLayout(self.tab2.layout7)
        self.tab2.layout.addStretch()
        self.tab2.setLayout(self.tab2.layout)

        # Tab 3
        self.tab3.layout = QVBoxLayout(self)
        # label_searchdir
        self.tab3.label_searchdir = QLabel("搜索目录：")
        # textbox_searchdir
        self.tab3.textbox_searchdir = QLineEdit(self)
        # button_searchdir
        self.tab3.button_searchdir = QPushButton("选择目录")
        self.tab3.button_searchdir.clicked.connect(self.tab3_searchdir_click)
        # label_searchtype
        self.tab3.label_searchtype = QLabel("类型：")
        # buttongroup_searchtype
        self.tab3.buttongroup_searchtype = QButtonGroup(self)
        # radiobutton_image
        self.tab3.radiobutton_image = QRadioButton("图片")
        self.tab3.radiobutton_image.setFixedWidth(60)
        self.tab3.radiobutton_image.setChecked(True)
        # combobox_image
        self.tab3.combobox_image = QComboBox(self)
        self.tab3.combobox_image.setFixedWidth(80)
        self.tab3.combobox_image.addItem("所有")
        for i in image_format:
            self.tab3.combobox_image.addItem("." + i)
        # radiobutton_audio
        self.tab3.radiobutton_audio = QRadioButton("音频")
        self.tab3.radiobutton_audio.setFixedWidth(60)
        # combobox_audio
        self.tab3.combobox_audio = QComboBox(self)
        self.tab3.combobox_audio.setFixedWidth(80)
        self.tab3.combobox_audio.addItem("所有")
        for i in audio_format:
            self.tab3.combobox_audio.addItem("." + i)
        # radiobutton_video
        self.tab3.radiobutton_video = QRadioButton("视频")
        self.tab3.radiobutton_video.setFixedWidth(60)
        # combobox_video
        self.tab3.combobox_video = QComboBox(self)
        self.tab3.combobox_video.setFixedWidth(80)
        self.tab3.combobox_video.addItem("所有")
        for i in video_format:
            self.tab3.combobox_video.addItem("." + i)
        # button_search
        self.tab3.button_search = QPushButton("搜索")
        self.tab3.button_search.clicked.connect(self.tab3_search_click)
        # label_searchsize
        self.tab3.label_searchsize = QLabel("大小：")
        # buttongroup_searchsize
        self.tab3.buttongroup_searchsize = QButtonGroup(self)
        # radiobutton_sizeoff
        self.tab3.radiobutton_sizeoff = QRadioButton("无限制")
        self.tab3.radiobutton_sizeoff.setChecked(True)
        # radiobutton_sizeon
        self.tab3.radiobutton_sizeon = QRadioButton("自定义")
        # label_sizesm
        self.tab3.label_sizesm = QLabel("大于")
        self.tab3.label_sizesm.setFixedWidth(30)
        # textbox_sizesm
        self.tab3.textbox_sizesm = QLineEdit("0")
        self.tab3.textbox_sizesm.setFixedWidth(60)
        # combobox_sizesm
        self.tab3.combobox_sizesm = QComboBox(self)
        self.tab3.combobox_sizesm.setFixedWidth(80)
        self.tab3.combobox_sizesm.addItem("KB")
        self.tab3.combobox_sizesm.addItem("MB")
        self.tab3.combobox_sizesm.addItem("GB")
        # label_sizebg
        self.tab3.label_sizebg = QLabel("小于")
        self.tab3.label_sizebg.setFixedWidth(30)
        # textbox_sizebg
        self.tab3.textbox_sizebg = QLineEdit("512")
        self.tab3.textbox_sizebg.setFixedWidth(60)
        # combobox_sizebg
        self.tab3.combobox_sizebg = QComboBox(self)
        self.tab3.combobox_sizebg.setFixedWidth(80)
        self.tab3.combobox_sizebg.addItem("KB")
        self.tab3.combobox_sizebg.addItem("MB")
        self.tab3.combobox_sizebg.addItem("GB")
        self.tab3.combobox_sizebg.setCurrentIndex(1)
        # label_searchtime
        self.tab3.label_searchtime = QLabel("修改时间：")
        # buttongroup_searchtime
        self.tab3.buttongroup_searchtime = QButtonGroup(self)
        # radiobutton_timeoff
        self.tab3.radiobutton_timeoff = QRadioButton("无限制")
        self.tab3.radiobutton_timeoff.setChecked(True)
        # radiobutton_timeon
        self.tab3.radiobutton_timeon = QRadioButton("自定义")
        # label_timesm
        self.tab3.label_timesm = QLabel("大于")
        self.tab3.label_timesm.setFixedWidth(30)
        # datetime_timesm
        self.tab3.datetime_timesm = QDateTimeEdit(self)
        self.tab3.datetime_timesm.setCalendarPopup(True)
        self.tab3.datetime_timesm_dt = QDateTime()
        self.tab3.datetime_timesm_dt.setTime_t(time.time() - 1296000)
        self.tab3.datetime_timesm.setDateTime(self.tab2.datetime_timesm_dt)
        # label_timebg
        self.tab3.label_timebg = QLabel("小于")
        self.tab3.label_timebg.setFixedWidth(30)
        # datetime_timebg
        self.tab3.datetime_timebg = QDateTimeEdit(self)
        self.tab3.datetime_timebg.setCalendarPopup(True)
        self.tab3.datetime_timebg_dt = QDateTime()
        self.tab3.datetime_timebg_dt.setTime_t(time.time())
        self.tab3.datetime_timebg.setDateTime(self.tab2.datetime_timebg_dt)
        # label_searchresult
        self.tab3.label_searchresult = QLabel("搜索结果：")
        # list_searchresult
        self.tab3.list_searchresult = QListWidget(self)
        # Add widgets to tab
        self.tab3.layout1 = QHBoxLayout(self)
        self.tab3.layout2 = QHBoxLayout(self)
        self.tab3.layout3 = QHBoxLayout(self)
        self.tab3.layout4 = QHBoxLayout(self)
        self.tab3.layout5 = QHBoxLayout(self)
        self.tab3.layout6 = QHBoxLayout(self)
        self.tab3.layout1.addWidget(self.tab3.label_searchdir)
        self.tab3.layout1.addWidget(self.tab3.textbox_searchdir)
        self.tab3.layout1.addWidget(self.tab3.button_searchdir)
        self.tab3.layout2.addWidget(self.tab3.label_searchtype)
        self.tab3.layout2.addStretch()
        self.tab3.buttongroup_searchtype.addButton(self.tab3.radiobutton_image)
        self.tab3.buttongroup_searchtype.addButton(self.tab3.radiobutton_audio)
        self.tab3.buttongroup_searchtype.addButton(self.tab3.radiobutton_video)
        self.tab3.layout2.addWidget(self.tab3.radiobutton_image)
        self.tab3.layout2.addWidget(self.tab3.combobox_image)
        self.tab3.layout2.addStretch()
        self.tab3.layout2.addWidget(self.tab3.radiobutton_audio)
        self.tab3.layout2.addWidget(self.tab3.combobox_audio)
        self.tab3.layout2.addStretch()
        self.tab3.layout2.addWidget(self.tab3.radiobutton_video)
        self.tab3.layout2.addWidget(self.tab3.combobox_video)
        self.tab3.layout2.addStretch()
        self.tab3.layout2.addWidget(self.tab3.button_search)
        self.tab3.layout3.addWidget(self.tab3.label_searchsize)
        self.tab3.buttongroup_searchsize.addButton(self.tab3.radiobutton_sizeoff)
        self.tab3.buttongroup_searchsize.addButton(self.tab3.radiobutton_sizeon)
        self.tab3.layout3.addWidget(self.tab3.radiobutton_sizeoff)
        self.tab3.layout3.addWidget(self.tab3.radiobutton_sizeon)
        self.tab3.layout3.addWidget(self.tab3.label_sizesm)
        self.tab3.layout3.addWidget(self.tab3.textbox_sizesm)
        self.tab3.layout3.addWidget(self.tab3.combobox_sizesm)
        self.tab3.layout3.addWidget(self.tab3.label_sizebg)
        self.tab3.layout3.addWidget(self.tab3.textbox_sizebg)
        self.tab3.layout3.addWidget(self.tab3.combobox_sizebg)
        self.tab3.layout4.addWidget(self.tab3.label_searchtime)
        self.tab3.buttongroup_searchtime.addButton(self.tab3.radiobutton_timeoff)
        self.tab3.buttongroup_searchtime.addButton(self.tab3.radiobutton_timeon)
        self.tab3.layout4.addWidget(self.tab3.radiobutton_timeoff)
        self.tab3.layout4.addWidget(self.tab3.radiobutton_timeon)
        self.tab3.layout4.addWidget(self.tab3.label_timesm)
        self.tab3.layout4.addWidget(self.tab3.datetime_timesm)
        self.tab3.layout4.addWidget(self.tab3.label_timebg)
        self.tab3.layout4.addWidget(self.tab3.datetime_timebg)
        self.tab3.layout5.addWidget(self.tab3.label_searchresult)
        self.tab3.layout6.addWidget(self.tab3.list_searchresult)
        self.tab3.layout.addLayout(self.tab3.layout1)
        self.tab3.layout.addLayout(self.tab3.layout2)
        self.tab3.layout.addLayout(self.tab3.layout3)
        self.tab3.layout.addLayout(self.tab3.layout4)
        self.tab3.layout.addStretch()
        self.tab3.layout.addLayout(self.tab3.layout5)
        self.tab3.layout.addLayout(self.tab3.layout6)
        self.tab3.layout.addStretch()
        self.tab3.setLayout(self.tab3.layout)

        # Tab 4
        self.tab4.layout = QVBoxLayout(self)
        # label_searchdir
        self.tab4.label_searchdir = QLabel("搜索目录：")
        # textbox_searchdir
        self.tab4.textbox_searchdir = QLineEdit(self)
        # button_searchdir
        self.tab4.button_searchdir = QPushButton("选择目录")
        self.tab4.button_searchdir.clicked.connect(self.tab4_searchdir_click)
        # label_searchpic
        self.tab4.label_searchpic = QLabel("源图片：")
        # textbox_search
        self.tab4.textbox_search = QLineEdit(self)
        # button_searchpic
        self.tab4.button_searchpic = QPushButton("选择图片")
        self.tab4.button_searchpic.clicked.connect(self.tab4_searchpic_click)
        # button_search
        self.tab4.button_search = QPushButton("搜索")
        self.tab4.button_search.clicked.connect(self.tab4_search_click)
        # label_searchsize
        self.tab4.label_searchsize = QLabel("大小：")
        # buttongroup_searchsize
        self.tab4.buttongroup_searchsize = QButtonGroup(self)
        # radiobutton_sizeoff
        self.tab4.radiobutton_sizeoff = QRadioButton("无限制")
        self.tab4.radiobutton_sizeoff.setChecked(True)
        # radiobutton_sizeon
        self.tab4.radiobutton_sizeon = QRadioButton("自定义")
        # label_sizesm
        self.tab4.label_sizesm = QLabel("大于")
        self.tab4.label_sizesm.setFixedWidth(30)
        # textbox_sizesm
        self.tab4.textbox_sizesm = QLineEdit("0")
        self.tab4.textbox_sizesm.setFixedWidth(60)
        # combobox_sizesm
        self.tab4.combobox_sizesm = QComboBox(self)
        self.tab4.combobox_sizesm.setFixedWidth(80)
        self.tab4.combobox_sizesm.addItem("KB")
        self.tab4.combobox_sizesm.addItem("MB")
        self.tab4.combobox_sizesm.addItem("GB")
        # label_sizebg
        self.tab4.label_sizebg = QLabel("小于")
        self.tab4.label_sizebg.setFixedWidth(30)
        # textbox_sizebg
        self.tab4.textbox_sizebg = QLineEdit("512")
        self.tab4.textbox_sizebg.setFixedWidth(60)
        # combobox_sizebg
        self.tab4.combobox_sizebg = QComboBox(self)
        self.tab4.combobox_sizebg.setFixedWidth(80)
        self.tab4.combobox_sizebg.addItem("KB")
        self.tab4.combobox_sizebg.addItem("MB")
        self.tab4.combobox_sizebg.addItem("GB")
        self.tab4.combobox_sizebg.setCurrentIndex(1)
        # label_searchtime
        self.tab4.label_searchtime = QLabel("修改时间：")
        # buttongroup_searchtime
        self.tab4.buttongroup_searchtime = QButtonGroup(self)
        # radiobutton_timeoff
        self.tab4.radiobutton_timeoff = QRadioButton("无限制")
        self.tab4.radiobutton_timeoff.setChecked(True)
        # radiobutton_timeon
        self.tab4.radiobutton_timeon = QRadioButton("自定义")
        # label_timesm
        self.tab4.label_timesm = QLabel("大于")
        self.tab4.label_timesm.setFixedWidth(30)
        # datetime_timesm
        self.tab4.datetime_timesm = QDateTimeEdit(self)
        self.tab4.datetime_timesm.setCalendarPopup(True)
        self.tab4.datetime_timesm_dt = QDateTime()
        self.tab4.datetime_timesm_dt.setTime_t(time.time() - 1296000)
        self.tab4.datetime_timesm.setDateTime(self.tab2.datetime_timesm_dt)
        # label_timebg
        self.tab4.label_timebg = QLabel("小于")
        self.tab4.label_timebg.setFixedWidth(30)
        # datetime_timebg
        self.tab4.datetime_timebg = QDateTimeEdit(self)
        self.tab4.datetime_timebg.setCalendarPopup(True)
        self.tab4.datetime_timebg_dt = QDateTime()
        self.tab4.datetime_timebg_dt.setTime_t(time.time())
        self.tab4.datetime_timebg.setDateTime(self.tab2.datetime_timebg_dt)
        # label_searchresult
        self.tab4.label_searchresult = QLabel("搜索结果：")
        # list_searchresult
        self.tab4.list_searchresult = QListWidget(self)
        # Add widgets to tab
        self.tab4.layout1 = QHBoxLayout(self)
        self.tab4.layout2 = QHBoxLayout(self)
        self.tab4.layout3 = QHBoxLayout(self)
        self.tab4.layout4 = QHBoxLayout(self)
        self.tab4.layout5 = QHBoxLayout(self)
        self.tab4.layout6 = QHBoxLayout(self)
        self.tab4.layout1.addWidget(self.tab4.label_searchdir)
        self.tab4.layout1.addWidget(self.tab4.textbox_searchdir)
        self.tab4.layout1.addWidget(self.tab4.button_searchdir)
        self.tab4.layout2.addWidget(self.tab4.label_searchpic)
        self.tab4.layout2.addWidget(self.tab4.textbox_search)
        self.tab4.layout2.addWidget(self.tab4.button_searchpic)
        self.tab4.layout2.addWidget(self.tab4.button_search)
        self.tab4.layout3.addWidget(self.tab4.label_searchsize)
        self.tab4.buttongroup_searchsize.addButton(self.tab4.radiobutton_sizeoff)
        self.tab4.buttongroup_searchsize.addButton(self.tab4.radiobutton_sizeon)
        self.tab4.layout3.addWidget(self.tab4.radiobutton_sizeoff)
        self.tab4.layout3.addWidget(self.tab4.radiobutton_sizeon)
        self.tab4.layout3.addWidget(self.tab4.label_sizesm)
        self.tab4.layout3.addWidget(self.tab4.textbox_sizesm)
        self.tab4.layout3.addWidget(self.tab4.combobox_sizesm)
        self.tab4.layout3.addWidget(self.tab4.label_sizebg)
        self.tab4.layout3.addWidget(self.tab4.textbox_sizebg)
        self.tab4.layout3.addWidget(self.tab4.combobox_sizebg)
        self.tab4.layout4.addWidget(self.tab4.label_searchtime)
        self.tab4.buttongroup_searchtime.addButton(self.tab4.radiobutton_timeoff)
        self.tab4.buttongroup_searchtime.addButton(self.tab4.radiobutton_timeon)
        self.tab4.layout4.addWidget(self.tab4.radiobutton_timeoff)
        self.tab4.layout4.addWidget(self.tab4.radiobutton_timeon)
        self.tab4.layout4.addWidget(self.tab4.label_timesm)
        self.tab4.layout4.addWidget(self.tab4.datetime_timesm)
        self.tab4.layout4.addWidget(self.tab4.label_timebg)
        self.tab4.layout4.addWidget(self.tab4.datetime_timebg)
        self.tab4.layout5.addWidget(self.tab4.label_searchresult)
        self.tab4.layout6.addWidget(self.tab4.list_searchresult)
        self.tab4.layout.addLayout(self.tab4.layout1)
        self.tab4.layout.addLayout(self.tab4.layout2)
        self.tab4.layout.addLayout(self.tab4.layout3)
        self.tab4.layout.addLayout(self.tab4.layout4)
        self.tab4.layout.addStretch()
        self.tab4.layout.addLayout(self.tab4.layout5)
        self.tab4.layout.addLayout(self.tab4.layout6)
        self.tab4.layout.addStretch()
        self.tab4.setLayout(self.tab4.layout)

        # Tab 5
        self.tab5.layout = QVBoxLayout(self)
        # label_recoverfile
        self.tab5.label_recoverfile = QLabel("镜像文件：")
        # textbox_recoverfile
        self.tab5.textbox_recoverfile = QLineEdit(self)
        # button_recoverfile
        self.tab5.button_recoverfile = QPushButton("选择文件")
        self.tab5.button_recoverfile.clicked.connect(self.tab5_recoverfile_click)
        # label_recoverdir
        self.tab5.label_recoverdir = QLabel("输出目录：")
        # textbox_recoverdir
        self.tab5.textbox_recoverdir = QLineEdit(self)
        # button_recoverdir
        self.tab5.button_recoverdir = QPushButton("选择目录")
        self.tab5.button_recoverdir.clicked.connect(self.tab5_recoverdir_click)
        # button_recover
        self.tab5.button_recover = QPushButton("恢复")
        self.tab5.button_recover.clicked.connect(self.tab5_recover_click)
        # label_recoveroption
        self.tab5.label_recoveroption = QLabel("选项：")
        # checkbox_indirect
        self.tab5.checkbox_indirect = QCheckBox("间接块检测（仅支持UNIX文件系统）")
        # checkbox_corrupted
        self.tab5.checkbox_corrupted = QCheckBox("写出所有文件头（无纠错检测）")
        # checkbox_quick
        self.tab5.checkbox_quick = QCheckBox("快速模式（按512字节搜索）")
        # label_recovertype
        self.tab5.label_recovertype = QLabel("类型：")
        # buttongroup_recovertype
        self.tab5.buttongroup_recovertype = QButtonGroup(self)
        # radiobutton_all
        self.tab5.radiobutton_all = QRadioButton("所有已知")
        self.tab5.radiobutton_all.setChecked(True)
        # radiobutton_image
        self.tab5.radiobutton_image = QRadioButton("图片")
        # radiobutton_media
        self.tab5.radiobutton_media = QRadioButton("音视频")
        # radiobutton_document
        self.tab5.radiobutton_document = QRadioButton("文档")
        # radiobutton_other
        self.tab5.radiobutton_other = QRadioButton("其它")
        # label_recovertype_empty
        self.tab5.label_recovertype_empty = QLabel(self)
        self.tab5.label_recovertype_empty.setFixedWidth(200)
        # list_recovertype_image
        self.tab5.list_recovertype_image = QListWidget(self)
        self.tab5.list_recovertype_image.setFixedWidth(100)
        self.tab5.list_recovertype_image.setFixedHeight(120)
        self.tab5.list_recovertype_image.setSelectionMode(2)
        for i in recover_image_format:
            self.tab5.list_recovertype_image.addItem(i)
        # list_recovertype_media
        self.tab5.list_recovertype_media = QListWidget(self)
        self.tab5.list_recovertype_media.setFixedWidth(100)
        self.tab5.list_recovertype_media.setFixedHeight(120)
        self.tab5.list_recovertype_media.setSelectionMode(2)
        for i in recover_media_format:
            self.tab5.list_recovertype_media.addItem(i)
        # list_recovertype_document
        self.tab5.list_recovertype_document = QListWidget(self)
        self.tab5.list_recovertype_document.setFixedWidth(100)
        self.tab5.list_recovertype_document.setFixedHeight(120)
        self.tab5.list_recovertype_document.setSelectionMode(2)
        for i in recover_document_format:
            self.tab5.list_recovertype_document.addItem(i)
        # list_recovertype_other
        self.tab5.list_recovertype_other = QListWidget(self)
        self.tab5.list_recovertype_other.setFixedWidth(100)
        self.tab5.list_recovertype_other.setFixedHeight(120)
        self.tab5.list_recovertype_other.setSelectionMode(2)
        for i in recover_other_format:
            self.tab5.list_recovertype_other.addItem(i)
        # label_recoverresult
        self.tab5.label_recoverresult = QLabel("恢复结果：")
        # list_recoverresult
        self.tab5.list_recoverresult = QListWidget(self)
        # Add widgets to tab
        self.tab5.layout1 = QHBoxLayout(self)
        self.tab5.layout2 = QHBoxLayout(self)
        self.tab5.layout3 = QHBoxLayout(self)
        self.tab5.layout4 = QHBoxLayout(self)
        self.tab5.layout5 = QHBoxLayout(self)
        self.tab5.layout6 = QHBoxLayout(self)
        self.tab5.layout7 = QHBoxLayout(self)
        self.tab5.layout1.addWidget(self.tab5.label_recoverfile)
        self.tab5.layout1.addWidget(self.tab5.textbox_recoverfile)
        self.tab5.layout1.addWidget(self.tab5.button_recoverfile)
        self.tab5.layout2.addWidget(self.tab5.label_recoverdir)
        self.tab5.layout2.addWidget(self.tab5.textbox_recoverdir)
        self.tab5.layout2.addWidget(self.tab5.button_recoverdir)
        self.tab5.layout2.addWidget(self.tab5.button_recover)
        self.tab5.layout3.addWidget(self.tab5.label_recoveroption)
        self.tab5.layout3.addWidget(self.tab5.checkbox_indirect)
        self.tab5.layout3.addWidget(self.tab5.checkbox_corrupted)
        self.tab5.layout3.addWidget(self.tab5.checkbox_quick)
        self.tab5.layout4.addWidget(self.tab5.label_recovertype)
        self.tab5.buttongroup_recovertype.addButton(self.tab5.radiobutton_all)
        self.tab5.buttongroup_recovertype.addButton(self.tab5.radiobutton_image)
        self.tab5.buttongroup_recovertype.addButton(self.tab5.radiobutton_media)
        self.tab5.buttongroup_recovertype.addButton(self.tab5.radiobutton_document)
        self.tab5.buttongroup_recovertype.addButton(self.tab5.radiobutton_other)
        self.tab5.layout4.addWidget(self.tab5.radiobutton_all)
        self.tab5.layout4.addWidget(self.tab5.radiobutton_image)
        self.tab5.layout4.addWidget(self.tab5.radiobutton_media)
        self.tab5.layout4.addWidget(self.tab5.radiobutton_document)
        self.tab5.layout4.addWidget(self.tab5.radiobutton_other)
        self.tab5.layout5.addWidget(self.tab5.label_recovertype_empty)
        self.tab5.layout5.addWidget(self.tab5.list_recovertype_image)
        self.tab5.layout5.addWidget(self.tab5.list_recovertype_media)
        self.tab5.layout5.addWidget(self.tab5.list_recovertype_document)
        self.tab5.layout5.addWidget(self.tab5.list_recovertype_other)
        self.tab5.layout6.addWidget(self.tab5.label_recoverresult)
        self.tab5.layout7.addWidget(self.tab5.list_recoverresult)
        self.tab5.layout.addLayout(self.tab5.layout1)
        self.tab5.layout.addLayout(self.tab5.layout2)
        self.tab5.layout.addLayout(self.tab5.layout3)
        self.tab5.layout.addLayout(self.tab5.layout4)
        self.tab5.layout.addLayout(self.tab5.layout5)
        self.tab5.layout.addStretch()
        self.tab5.layout.addLayout(self.tab5.layout6)
        self.tab5.layout.addLayout(self.tab5.layout7)
        self.tab5.layout.addStretch()
        self.tab5.setLayout(self.tab5.layout)

        # Tab 6
        self.tab6.layout = QVBoxLayout(self)
        # label_gpsdir
        self.tab6.label_gpsdir = QLabel("目标目录：")
        # textbox_gpsdir
        self.tab6.textbox_gpsdir = QLineEdit(self)
        # button_gpsdir
        self.tab6.button_gpsdir = QPushButton("选择目录")
        self.tab6.button_gpsdir.clicked.connect(self.tab6_gpsdir_click)
        # button_search
        self.tab6.button_search = QPushButton("搜索")
        self.tab6.button_search.clicked.connect(self.tab6_search_click)
        # label_searchresult
        self.tab6.label_searchresult = QLabel("搜索结果：")
        # button_drawmap
        self.tab6.button_drawmap = QPushButton("绘制地图")
        self.tab6.button_drawmap.clicked.connect(self.tab6_drawmap_click)
        self.tab6.button_drawmap.setFixedWidth(120)
        # list_searchresult
        self.tab6.list_searchresult = QListWidget(self)
        self.tab6.list_searchresult.setFixedHeight(150)
        # webview_map
        self.tab6.webview_map = QWebView(self)
        self.tab6.webview_map.load(QUrl(map_url))
        self.tab6.webview_map.show()
        # Add widgets to tab
        self.tab6.layout1 = QHBoxLayout(self)
        self.tab6.layout2 = QHBoxLayout(self)
        self.tab6.layout3 = QHBoxLayout(self)
        self.tab6.layout4 = QHBoxLayout(self)
        self.tab6.layout1.addWidget(self.tab6.label_gpsdir)
        self.tab6.layout1.addWidget(self.tab6.textbox_gpsdir)
        self.tab6.layout1.addWidget(self.tab6.button_gpsdir)
        self.tab6.layout1.addWidget(self.tab6.button_search)
        self.tab6.layout2.addWidget(self.tab6.label_searchresult)
        self.tab6.layout2.addWidget(self.tab6.button_drawmap)
        self.tab6.layout3.addWidget(self.tab6.list_searchresult)
        self.tab6.layout4.addWidget(self.tab6.webview_map)
        self.tab6.layout.addLayout(self.tab6.layout1)
        self.tab6.layout.addLayout(self.tab6.layout2)
        self.tab6.layout.addLayout(self.tab6.layout3)
        self.tab6.layout.addLayout(self.tab6.layout4)
        self.tab6.setLayout(self.tab6.layout)

        # Tab 7
        self.tab7.layout = QVBoxLayout(self)
        # label_searchdir
        self.tab7.label_searchdir = QLabel("目标目录：")
        # textbox_searchdir
        self.tab7.textbox_searchdir = QLineEdit(self)
        # button_searchdir
        self.tab7.button_searchdir = QPushButton("选择目录")
        self.tab7.button_searchdir.clicked.connect(self.tab7_searchdir_click)
        # button_search
        self.tab7.button_search = QPushButton("搜索")
        self.tab7.button_search.clicked.connect(self.tab7_search_click)
        # label_searchresult
        self.tab7.label_searchresult = QLabel("搜索结果：")
        # list_searchresult
        self.tab7.list_searchresult = QListWidget(self)
        self.tab7.list_searchresult.setFixedHeight(250)
        self.tab7.list_searchresult.itemDoubleClicked.connect(self.tab7_searchresult_doubleclick)
        # label_wechat
        self.tab7.label_wechat = QLabel("微信解密：")
        # label_imei
        self.tab7.label_imei = QLabel("IMEI：")
        # textbox_imei
        self.tab7.textbox_imei = QLineEdit(self)
        # label_uin
        self.tab7.label_uin = QLabel("UIN：")
        # textbox_uin
        self.tab7.textbox_uin = QLineEdit(self)
        # button_wechat
        self.tab7.button_wechat = QPushButton("计算密码")
        self.tab7.button_wechat.clicked.connect(self.tab7_wechat_click)
        # button_wechat_decrypt
        self.tab7.button_wechat_decrypt = QPushButton("解密文件")
        self.tab7.button_wechat_decrypt.clicked.connect(self.tab7_wechat_decrypt_click)
        # Add widgets to tab
        self.tab7.layout1 = QHBoxLayout(self)
        self.tab7.layout2 = QHBoxLayout(self)
        self.tab7.layout3 = QHBoxLayout(self)
        self.tab7.layout4 = QHBoxLayout(self)
        self.tab7.layout1.addWidget(self.tab7.label_searchdir)
        self.tab7.layout1.addWidget(self.tab7.textbox_searchdir)
        self.tab7.layout1.addWidget(self.tab7.button_searchdir)
        self.tab7.layout1.addWidget(self.tab7.button_search)
        self.tab7.layout2.addWidget(self.tab7.label_searchresult)
        self.tab7.layout3.addWidget(self.tab7.list_searchresult)
        self.tab7.layout4.addWidget(self.tab7.label_wechat)
        self.tab7.layout4.addWidget(self.tab7.label_imei)
        self.tab7.layout4.addWidget(self.tab7.textbox_imei)
        self.tab7.layout4.addWidget(self.tab7.label_uin)
        self.tab7.layout4.addWidget(self.tab7.textbox_uin)
        self.tab7.layout4.addWidget(self.tab7.button_wechat)
        self.tab7.layout4.addWidget(self.tab7.button_wechat_decrypt)
        self.tab7.layout.addLayout(self.tab7.layout1)
        self.tab7.layout.addLayout(self.tab7.layout2)
        self.tab7.layout.addLayout(self.tab7.layout3)
        self.tab7.layout.addLayout(self.tab7.layout4)
        self.tab7.layout.addStretch()
        self.tab7.setLayout(self.tab7.layout)

        # Add tabs to widget        
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

        # Tab Event
        self.tabs.currentChanged.connect(self.tabChanged)

        # Init Method
        self.tab1_refreshmount()

    def tabChanged(self):
        map_hideCpy(self.tab6.webview_map)

    def tab1_adb_click(self):
        saveFilePath = str(QFileDialog.getSaveFileName(self,"Save File","./","All Files (*)")[0])
        if saveFilePath:
            tab1_form1 = saveFilePath
            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Information)
            msgBox.setWindowTitle(' ')
            msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>提取中...<br></p>')
            msgBox.setStandardButtons(QMessageBox.Ok)
            okButton = msgBox.button(QMessageBox.Ok)
            okButton.setText('   取消   ')
            c = Tab1ADBThread()
            t = threading.Thread(target=c.run, args=(msgBox, tab1_form1))
            t.start()
            msgBox.exec_()
            if msgBox.clickedButton() == okButton: c.terminate()

    def tab1_openfile_click(self):
        global openFilePath, openFileName, pt_offset, pt_sector, pt_type, pt_name
        openFilePath = str(QFileDialog.getOpenFileName(self,"Select File","./","All Files (*)")[0])
        if openFilePath:
            openFileName = os.path.basename(openFilePath)
            pt_offset = []
            pt_sector = []
            pt_type = []
            pt_name = []
            self.tab1.list_filedetail.clear()
            sectorsize = int(self.tab1.textbox_sectorsize.text())
            sectoroffset = int(self.tab1.textbox_sectoroffset.text())
            findMBR(openFilePath,sectorsize,sectoroffset)
            for i in range(len(pt_offset)):
                sector_size = float(pt_sector[i])*sectorsize/1000/1000
                sector = "%.2fMB" % sector_size
                if sector_size > 1000:
                    sector_size = float(sector_size/1000)
                    sector = "%.2fGB" % sector_size
                self.tab1.list_filedetail.addItem(pt_type[i]+" ["+pt_name[i]+"] "+sector)

    def tab1_savefile_click(self):
        if len(pt_offset) < 1: return
        selectItems = self.tab1.list_filedetail.selectedItems()
        if len(selectItems) < 1: return
        saveFilePath = str(QFileDialog.getSaveFileName(self,"Save File","./","All Files (*)")[0])
        if saveFilePath:
            ptId = int(self.tab1.list_filedetail.row(selectItems[0]))
            tab1_form1 = openFilePath
            tab1_form2 = saveFilePath
            tab1_form3 = str(pt_offset[ptId])
            tab1_form4 = str(pt_sector[ptId])
            msgBox = QMessageBox()
            msgBox.setIcon(QMessageBox.Information)
            msgBox.setWindowTitle(' ')
            msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>保存中...<br></p>')
            msgBox.setStandardButtons(QMessageBox.Ok)
            okButton = msgBox.button(QMessageBox.Ok)
            okButton.setText('   取消   ')
            c = Tab1SaveFileThread()
            t = threading.Thread(target=c.run, args=(msgBox, tab1_form1, tab1_form2, tab1_form3, tab1_form4))
            t.start()
            msgBox.exec_()
            if msgBox.clickedButton() == okButton: c.terminate()

    def tab1_repairfile_click(self):
        imageFilePath = str(QFileDialog.getOpenFileName(self,"Select Image File","./","All Files (*)")[0])
        if imageFilePath:
            offset = int(self.tab1.textbox_sectoroffset.text())
            sector = int(self.tab1.textbox_sectorsize.text())
            blocksize_unit = int(self.tab1.textbox_blocksize.text())
            fd = open(imageFilePath,'rb')
            fd.seek(offset*sector)
            dbr = fd.read(sector*3)
            fd.close()
            blocksize = calcLen(dbr[sector*2+4:sector*2+8])
            os.system("truncate -s "+str(blocksize*blocksize_unit)+" "+imageFilePath)
            os.system("fsck."+self.tab1.textbox_repairfs.text()+" -y "+imageFilePath)

    def tab1_mountfile_click(self):
        mountFilePath = str(QFileDialog.getOpenFileName(self,"Select Mount File","./","All Files (*)")[0])
        if len(mountFilePath) < 1: return
        mountPath = str(QFileDialog.getExistingDirectory(self,"Select Mount Directory","./"))
        if mountPath:
            os.system("mount "+self.tab1.textbox_mountparams.text()+" "+mountFilePath+" "+mountPath)
            self.tab1_refreshmount()

    def tab1_umountdrive_click(self):
        selectItems = self.tab1.list_mountdetail.selectedItems()
        if len(selectItems) < 1: return
        mountId = int(self.tab1.list_mountdetail.row(selectItems[0]))
        os.system("umount "+mount_path[mountId])
        self.tab1_refreshmount()

    def tab1_refreshmount(self):
        global mount_dev, mount_path
        self.tab1.list_mountdetail.clear()
        mount_dev = []
        mount_path = []
        p = os.popen('mount')
        for line in p.readlines():
            temp = line.split(' ')
            if len(temp) < 3: continue
            if '/' in temp[0] and '/dev/sd' not in temp[0]:
                mount_dev.append(temp[0])
                mount_path.append(temp[2])
                self.tab1.list_mountdetail.addItem("%s on %s" % (temp[0], temp[2]) )
        p.close()

    def tab2_searchdir_click(self):
        searchdir = str(QFileDialog.getExistingDirectory(self,"Select Search Directory","./"))
        if searchdir:
            self.tab2.textbox_searchdir.setText(searchdir)

    def tab2_search_click(self):
        tab2_form1 = self.tab2.textbox_searchdir.text()
        tab2_form2 = self.tab2.textbox_search.text()
        tab2_form3 = self.tab2.radiobutton_string.isChecked()
        tab2_form4 = self.tab2.radiobutton_hex.isChecked()
        tab2_form5 = self.tab2.radiobutton_sizeoff.isChecked()
        tab2_form6 = self.tab2.radiobutton_sizeon.isChecked()
        tab2_form7 = self.tab2.textbox_sizesm.text()
        tab2_form8 = self.tab2.combobox_sizesm.currentIndex()
        tab2_form9 = self.tab2.textbox_sizebg.text()
        tab2_form10 = self.tab2.combobox_sizebg.currentIndex()
        tab2_form11 = self.tab2.radiobutton_timeoff.isChecked()
        tab2_form12 = self.tab2.radiobutton_timeon.isChecked()
        tab2_form13 = self.tab2.datetime_timesm.dateTime().toTime_t()
        tab2_form14 = self.tab2.datetime_timebg.dateTime().toTime_t()
        if not os.path.exists(tab2_form1):
            QMessageBox.information(self, ' ', '搜索目录不存在')
            return
        if not tab2_form2:
            QMessageBox.information(self, ' ', '请输入关键词')
            return
        if not tab2_form3 and not tab2_form4:
            QMessageBox.information(self, ' ', '请选择类型')
            return
        if not tab2_form5 and not tab2_form6:
            QMessageBox.information(self, ' ', '请选择大小')
            return
        if tab2_form6:
            form6_correct = True
            tab2_form7 = int(tab2_form7)
            tab2_form9 = int(tab2_form9)
            if tab2_form7 < 0 or tab2_form9 <= 0: form6_correct = False
            for i in range(tab2_form8 + 1): tab2_form7 = tab2_form7 * 1024
            for i in range(tab2_form10 + 1): tab2_form9 = tab2_form9 * 1024
            if tab2_form7 > tab2_form9: form6_correct = False
            if not form6_correct:
                QMessageBox.information(self, ' ', '请正确输入大小范围')
                return
        if not tab2_form11 and not tab2_form12:
            QMessageBox.information(self, ' ', '请选择修改时间')
            return
        if tab2_form12:
            form12_correct = True
            if tab2_form13 <= 0 or tab2_form14 <= 0: form12_correct = False
            if tab2_form13 > tab2_form14: form12_correct = False
            if not form12_correct:
                QMessageBox.information(self, ' ', '请正确输入修改时间范围')
                return
        if tab2_form3: tab2_form3 = 1
        if tab2_form4: tab2_form3 = 2
        if tab2_form5: tab2_form4 = 1
        if tab2_form6: tab2_form4 = 2
        tab2_form5 = 0
        tab2_form6 = 0
        if tab2_form4 == 2:
            tab2_form5 = tab2_form7
            tab2_form6 = tab2_form9
        if tab2_form11: tab2_form7 = 1
        if tab2_form12: tab2_form7 = 2
        tab2_form8 = 0
        tab2_form9 = 0
        if tab2_form7 == 2:
            tab2_form8 = tab2_form13
            tab2_form9 = tab2_form14
        tab2_form10 = self.tab2.list_searchresult
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>搜素中...<br></p>')
        msgBox.setStandardButtons(QMessageBox.Ok)
        okButton = msgBox.button(QMessageBox.Ok)
        okButton.setText('   取消   ')
        c = Tab2SearchThread()
        t = threading.Thread(target=c.run, args=(msgBox, tab2_form1, tab2_form2, tab2_form3, tab2_form4, tab2_form5, tab2_form6, tab2_form7, tab2_form8, tab2_form9, tab2_form10))
        t.start()
        msgBox.exec_()
        if msgBox.clickedButton() == okButton: c.terminate()

    def tab3_searchdir_click(self):
        searchdir = str(QFileDialog.getExistingDirectory(self,"Select Search Directory","./"))
        if searchdir:
            self.tab3.textbox_searchdir.setText(searchdir)

    def tab3_search_click(self):
        tab3_form1 = self.tab3.textbox_searchdir.text()
        tab3_form2 = self.tab3.radiobutton_image.isChecked()
        tab3_form3 = self.tab3.radiobutton_audio.isChecked()
        tab3_form4 = self.tab3.radiobutton_video.isChecked()
        tab3_form5 = self.tab3.combobox_image.currentIndex()
        tab3_form6 = self.tab3.combobox_audio.currentIndex()
        tab3_form7 = self.tab3.combobox_video.currentIndex()
        tab3_form8 = self.tab3.radiobutton_sizeoff.isChecked()
        tab3_form9 = self.tab3.radiobutton_sizeon.isChecked()
        tab3_form10 = self.tab3.textbox_sizesm.text()
        tab3_form11 = self.tab3.combobox_sizesm.currentIndex()
        tab3_form12 = self.tab3.textbox_sizebg.text()
        tab3_form13 = self.tab3.combobox_sizebg.currentIndex()
        tab3_form14 = self.tab3.radiobutton_timeoff.isChecked()
        tab3_form15 = self.tab3.radiobutton_timeon.isChecked()
        tab3_form16 = self.tab3.datetime_timesm.dateTime().toTime_t()
        tab3_form17 = self.tab3.datetime_timebg.dateTime().toTime_t()
        if not os.path.exists(tab3_form1):
            QMessageBox.information(self, ' ', '搜索目录不存在')
            return
        if not tab3_form2 and not tab3_form3 and not tab3_form4:
            QMessageBox.information(self, ' ', '请选择类型')
            return
        if not tab3_form8 and not tab3_form9:
            QMessageBox.information(self, ' ', '请选择大小')
            return
        if tab3_form9:
            form9_correct = True
            tab3_form10 = int(tab3_form10)
            tab3_form12 = int(tab3_form12)
            if tab3_form10 < 0 or tab3_form12 <= 0: form9_correct = False
            for i in range(tab3_form11 + 1): tab3_form10 = tab3_form10 * 1024
            for i in range(tab3_form13 + 1): tab3_form12 = tab3_form12 * 1024
            if tab3_form10 > tab3_form12: form9_correct = False
            if not form9_correct:
                QMessageBox.information(self, ' ', '请正确输入大小范围')
                return
        if not tab3_form14 and not tab3_form15:
            QMessageBox.information(self, ' ', '请选择修改时间')
            return
        if tab3_form15:
            form15_correct = True
            if tab3_form16 <= 0 or tab3_form17 <= 0: form15_correct = False
            if tab3_form16 > tab3_form17: form15_correct = False
            if not form15_correct:
                QMessageBox.information(self, ' ', '请正确输入修改时间范围')
                return
        if tab3_form2:
            tab3_form2 = 1
            tab3_form3 = tab3_form5
        elif tab3_form3:
            tab3_form2 = 2
            tab3_form3 = tab3_form6
        elif tab3_form4:
            tab3_form2 = 3
            tab3_form3 = tab3_form7
        if tab3_form8: tab3_form4 = 1
        if tab3_form9: tab3_form4 = 2
        tab3_form5 = 0
        tab3_form6 = 0
        if tab3_form4 == 2:
            tab3_form5 = tab3_form10
            tab3_form6 = tab3_form12
        if tab3_form14: tab3_form7 = 1
        if tab3_form15: tab3_form7 = 2
        tab3_form8 = 0
        tab3_form9 = 0
        if tab3_form7 == 2:
            tab3_form8 = tab3_form16
            tab3_form9 = tab3_form17
        tab3_form10 = self.tab3.list_searchresult
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>搜素中...<br></p>')
        msgBox.setStandardButtons(QMessageBox.Ok)
        okButton = msgBox.button(QMessageBox.Ok)
        okButton.setText('   取消   ')
        c = Tab3SearchThread()
        t = threading.Thread(target=c.run, args=(msgBox, tab3_form1, tab3_form2, tab3_form3, tab3_form4, tab3_form5, tab3_form6, tab3_form7, tab3_form8, tab3_form9, tab3_form10))
        t.start()
        msgBox.exec_()
        if msgBox.clickedButton() == okButton: c.terminate()

    def tab4_searchdir_click(self):
        searchdir = str(QFileDialog.getExistingDirectory(self,"Select Search Directory","./"))
        if searchdir:
            self.tab4.textbox_searchdir.setText(searchdir)

    def tab4_searchpic_click(self):
        searchpic = str(QFileDialog.getOpenFileName(self,"Select Source Image","./","All Files (*)")[0])
        if len(searchpic) < 1: return
        self.tab4.textbox_search.setText(searchpic)

    def tab4_search_click(self):
        tab4_form1 = self.tab4.textbox_searchdir.text()
        tab4_form2 = self.tab4.textbox_search.text()
        tab4_form3 = self.tab4.radiobutton_sizeoff.isChecked()
        tab4_form4 = self.tab4.radiobutton_sizeon.isChecked()
        tab4_form5 = self.tab4.textbox_sizesm.text()
        tab4_form6 = self.tab4.combobox_sizesm.currentIndex()
        tab4_form7 = self.tab4.textbox_sizebg.text()
        tab4_form8 = self.tab4.combobox_sizebg.currentIndex()
        tab4_form9 = self.tab4.radiobutton_timeoff.isChecked()
        tab4_form10 = self.tab4.radiobutton_timeon.isChecked()
        tab4_form11 = self.tab4.datetime_timesm.dateTime().toTime_t()
        tab4_form12 = self.tab4.datetime_timebg.dateTime().toTime_t()
        if not os.path.exists(tab4_form1):
            QMessageBox.information(self, ' ', '搜索目录不存在')
            return
        if not os.path.exists(tab4_form2):
            QMessageBox.information(self, ' ', '搜索源图片不存在')
            return
        if not tab4_form3 and not tab4_form4:
            QMessageBox.information(self, ' ', '请选择大小')
            return
        if tab4_form4:
            form4_correct = True
            tab4_form5 = int(tab4_form5)
            tab4_form7 = int(tab4_form7)
            if tab4_form5 < 0 or tab4_form7 <= 0: form4_correct = False
            for i in range(tab4_form6 + 1): tab4_form5 = tab4_form5 * 1024
            for i in range(tab4_form8 + 1): tab4_form7 = tab4_form7 * 1024
            if tab4_form5 > tab4_form7: form4_correct = False
            if not form4_correct:
                QMessageBox.information(self, ' ', '请正确输入大小范围')
                return
        if not tab4_form9 and not tab4_form10:
            QMessageBox.information(self, ' ', '请选择修改时间')
            return
        if tab4_form10:
            form10_correct = True
            if tab4_form11 <= 0 or tab4_form12 <= 0: form10_correct = False
            if tab4_form11 > tab4_form12: form10_correct = False
            if not form10_correct:
                QMessageBox.information(self, ' ', '请正确输入修改时间范围')
                return
        if tab4_form3: tab4_form3 = 1
        if tab4_form4: tab4_form3 = 2
        tab4_form4 = 0
        tab4_form5 = 0
        if tab4_form3 == 2:
            tab4_form4 = tab4_form5
            tab4_form5 = tab4_form7
        if tab4_form9: tab4_form6 = 1
        if tab4_form10: tab4_form6 = 2
        tab4_form7 = 0
        tab4_form8 = 0
        if tab4_form6 == 2:
            tab4_form7 = tab4_form11
            tab4_form8 = tab4_form12
        tab4_form9 = self.tab4.list_searchresult
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>搜素中...<br></p>')
        msgBox.setStandardButtons(QMessageBox.Ok)
        okButton = msgBox.button(QMessageBox.Ok)
        okButton.setText('   取消   ')
        c = Tab4SearchThread()
        t = threading.Thread(target=c.run, args=(msgBox, tab4_form1, tab4_form2, tab4_form3, tab4_form4, tab4_form5, tab4_form6, tab4_form7, tab4_form8, tab4_form9))
        t.start()
        msgBox.exec_()
        if msgBox.clickedButton() == okButton: c.terminate()

    def tab5_recoverfile_click(self):
        recoverfile = str(QFileDialog.getOpenFileName(self,"Select Image File","./","All Files (*)")[0])
        if len(recoverfile) < 1: return
        self.tab5.textbox_recoverfile.setText(recoverfile)

    def tab5_recoverdir_click(self):
        recoverdir = str(QFileDialog.getExistingDirectory(self,"Select Recover Output Directory","./"))
        if recoverdir:
            self.tab5.textbox_recoverdir.setText(recoverdir)

    def tab5_recover_click(self):
        tab5_form1 = self.tab5.textbox_recoverfile.text()
        tab5_form2 = self.tab5.textbox_recoverdir.text()
        tab5_form3 = self.tab5.checkbox_indirect.isChecked()
        tab5_form4 = self.tab5.checkbox_corrupted.isChecked()
        tab5_form5 = self.tab5.checkbox_quick.isChecked()
        tab5_form6 = self.tab5.radiobutton_all.isChecked()
        tab5_form7 = self.tab5.radiobutton_image.isChecked()
        tab5_form8 = self.tab5.radiobutton_media.isChecked()
        tab5_form9 = self.tab5.radiobutton_document.isChecked()
        tab5_form10 = self.tab5.radiobutton_other.isChecked()
        tab5_form11 = self.tab5.list_recovertype_image.selectedItems()
        tab5_form12 = self.tab5.list_recovertype_media.selectedItems()
        tab5_form13 = self.tab5.list_recovertype_document.selectedItems()
        tab5_form14 = self.tab5.list_recovertype_other.selectedItems()
        if not os.path.exists(tab5_form1):
            QMessageBox.information(self, ' ', '镜像文件不存在')
            return
        if not os.path.exists(tab5_form2):
            QMessageBox.information(self, ' ', '输出目录不存在')
            return
        if not tab5_form6 and not tab5_form7 and not tab5_form8 and not tab5_form9 and not tab5_form10:
            QMessageBox.information(self, ' ', '请选择类型')
            return
        if tab5_form6: tab5_form6 = 1
        if tab5_form7: tab5_form6 = 2
        if tab5_form8: tab5_form6 = 3
        if tab5_form9: tab5_form6 = 4
        if tab5_form10: tab5_form6 = 5
        tab5_form7 = ""
        if tab5_form6 == 2:
            if len(tab5_form11) > 0:
                tab5_form11_text = []
                for i in tab5_form11:
                    tab5_form11_text.append(i.text())
                tab5_form7 = ','.join(tab5_form11_text)
            else:
                tab5_form7 = ','.join(recover_image_format)
        if tab5_form6 == 3:
            if len(tab5_form12) > 0:
                tab5_form12_text = []
                for i in tab5_form12:
                    tab5_form12_text.append(i.text())
                tab5_form7 = ','.join(tab5_form12_text)
            else:
                tab5_form7 = ','.join(recover_media_format)
        if tab5_form6 == 4:
            if len(tab5_form13) > 0:
                tab5_form13_text = []
                for i in tab5_form13:
                    tab5_form13_text.append(i.text())
                tab5_form7 = ','.join(tab5_form13_text)
            else:
                tab5_form7 = ','.join(recover_document_format)
        if tab5_form6 == 5:
            if len(tab5_form14) > 0:
                tab5_form14_text = []
                for i in tab5_form14:
                    tab5_form14_text.append(i.text())
                tab5_form7 = ','.join(tab5_form14_text)
            else:
                tab5_form7 = ','.join(recover_other_format)
        tab5_form8 = self.tab5.list_recoverresult
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>恢复中...<br></p>')
        msgBox.setStandardButtons(QMessageBox.Ok)
        okButton = msgBox.button(QMessageBox.Ok)
        okButton.setText('   取消   ')
        c = Tab5RecoverThread()
        t = threading.Thread(target=c.run, args=(msgBox, tab5_form1, tab5_form2, tab5_form3, tab5_form4, tab5_form5, tab5_form6, tab5_form7, tab5_form8))
        t.start()
        msgBox.exec_()
        if msgBox.clickedButton() == okButton: c.terminate()

    def tab6_gpsdir_click(self):
        gpsdir = str(QFileDialog.getExistingDirectory(self,"Select Target Directory","./"))
        if gpsdir:
            self.tab6.textbox_gpsdir.setText(gpsdir)

    def tab6_search_click(self):
        tab6_form1 = self.tab6.textbox_gpsdir.text()
        if not os.path.exists(tab6_form1):
            QMessageBox.information(self, ' ', '目标目录不存在')
            return
        tab6_form2 = self.tab6.list_searchresult
        tab6_form3 = self.tab6.webview_map
        map_data = []
        tab6_form3.page().mainFrame().evaluateJavaScript("map.clearOverlays();")
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>搜索中...<br></p>')
        msgBox.setStandardButtons(QMessageBox.Ok)
        okButton = msgBox.button(QMessageBox.Ok)
        okButton.setText('   取消   ')
        c = Tab6GPSThread()
        t = threading.Thread(target=c.run, args=(msgBox, tab6_form1, tab6_form2, tab6_form3))
        t.start()
        msgBox.exec_()
        if msgBox.clickedButton() == okButton: c.terminate()

    def tab6_drawmap_click(self):
        if len(map_data) <= 0: return
        webView = self.tab6.webview_map
        webView.page().mainFrame().evaluateJavaScript("map.clearOverlays();")
        map_data_sorted = sorted(map_data, key=lambda metadata: metadata[0])
        pre_metadata = 0
        for metadata in map_data_sorted:
            webView.page().mainFrame().evaluateJavaScript("map.addOverlay(new BMap.Marker(new BMap.Point(%f, %f)));" % (metadata[2], metadata[1]) )
            if pre_metadata != 0:
                webView.page().mainFrame().evaluateJavaScript("map.addOverlay(new BMap.Polyline([new BMap.Point(%f, %f), new BMap.Point(%f, %f)], {strokeColor: 'blue', strokeWeight: 6, strokeOpacity: 0.5}));" % (pre_metadata[2], pre_metadata[1], metadata[2], metadata[1]) )
            pre_metadata = metadata
        center_lat, center_lon = map_getCenter()
        webView.page().mainFrame().evaluateJavaScript("map.centerAndZoom(new BMap.Point(%f, %f), %d);" % (center_lon, center_lat, map_getZoom()) )

    def tab7_searchdir_click(self):
        searchdir = str(QFileDialog.getExistingDirectory(self,"Select Search Directory","./"))
        if searchdir:
            self.tab7.textbox_searchdir.setText(searchdir)

    def tab7_search_click(self):
        tab7_form1 = self.tab7.textbox_searchdir.text()
        if not os.path.exists(tab7_form1):
            QMessageBox.information(self, ' ', '搜索目录不存在')
            return
        tab7_form2 = self.tab7.list_searchresult
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>搜素中...<br></p>')
        msgBox.setStandardButtons(QMessageBox.Ok)
        okButton = msgBox.button(QMessageBox.Ok)
        okButton.setText('   取消   ')
        c = Tab7SearchThread()
        t = threading.Thread(target=c.run, args=(msgBox, tab7_form1, tab7_form2))
        t.start()
        msgBox.exec_()
        if msgBox.clickedButton() == okButton: c.terminate()

    def tab7_searchresult_doubleclick(self):
        db_file = self.tab7.list_searchresult.currentItem().text().replace('DB: ','')
        subprocess.Popen(['sqlitebrowser', db_file])

    def tab7_wechat_click(self):
        tab7_form1 = self.tab7.textbox_imei.text()
        tab7_form2 = self.tab7.textbox_uin.text()
        if len(tab7_form1.strip()) <= 0:
            QMessageBox.information(self, ' ', '请输入IMEI')
            return
        if len(tab7_form2.strip()) <= 0:
            QMessageBox.information(self, ' ', '请输入UIN')
            return
        tab7_raw = "%s%s" % (tab7_form1.strip(), tab7_form2.strip())
        tab7_md5 = hashlib.md5(tab7_raw.encode('utf-8')).hexdigest()
        QMessageBox.information(self, ' ', '数据库密码：%s' % tab7_md5[:7])

    def tab7_wechat_decrypt_click(self):
        tab7_form1 = self.tab7.textbox_imei.text()
        tab7_form2 = self.tab7.textbox_uin.text()
        if len(tab7_form1.strip()) <= 0:
            QMessageBox.information(self, ' ', '请输入IMEI')
            return
        if len(tab7_form2.strip()) <= 0:
            QMessageBox.information(self, ' ', '请输入UIN')
            return
        tab7_form3 = str(QFileDialog.getOpenFileName(self,"Select Encrypted Database File","./","All Files (*)")[0])
        if len(tab7_form3) < 1: return
        tab7_form4 = str(QFileDialog.getSaveFileName(self,"Save Decrypted Database File","./","All Files (*)")[0])
        if not tab7_form4: return
        tab7_raw = "%s%s" % (tab7_form1.strip(), tab7_form2.strip())
        tab7_md5 = hashlib.md5(tab7_raw.encode('utf-8')).hexdigest()
        tab7_form1 = tab7_form3
        tab7_form2 = tab7_md5[:7]
        tab7_form3 = tab7_form4
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(' ')
        msgBox.setText('<p align="center" style="margin-left:20px;margin-right:35px;"><br>解密中...<br></p>')
        msgBox.setStandardButtons(QMessageBox.Ok)
        okButton = msgBox.button(QMessageBox.Ok)
        okButton.setText('   取消   ')
        c = Tab7DecryptThread()
        t = threading.Thread(target=c.run, args=(msgBox, tab7_form1, tab7_form2, tab7_form3))
        t.start()
        msgBox.exec_()
        if msgBox.clickedButton() == okButton: c.terminate()

class Tab1ADBThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, msgbox, saveFilePath):
        time.sleep(1)
        with open(saveFilePath, 'wb') as outfile:
            process = None
            process = subprocess.Popen(['adb', 'shell', 'su', '-c', 'dd if=/dev/block/mmcblk0 2>/dev/null'], stdout=outfile, stderr=subprocess.PIPE)
            while process:
                if not self._running:
                    process.kill()
                    break
                if process.poll() != None: break
        msgbox.done(0)

class Tab1SaveFileThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, msgbox, openFilePath, saveFilePath, skipOffset, countSector):
        time.sleep(1)
        process = None
        process = subprocess.Popen(['dd', 'if='+openFilePath, "of="+saveFilePath, "bs=512", "skip="+skipOffset, "count="+countSector], stdout=subprocess.PIPE)
        while process:
            if not self._running:
                process.kill()
                break
            if process.poll() != None: break
        msgbox.done(0)

class Tab2SearchThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, msgbox, path, keyword, search_type, search_size, size_sm, size_bg, search_time, time_sm, time_bg, listView):
        listView.clear()
        time.sleep(1)
        process = None
        if search_type == 1:
            process = subprocess.Popen(['grep', '-rl', keyword, path], stdout=subprocess.PIPE)
        if search_type == 2:
            if len(keyword) % 2 == 1: keyword = "0" + keyword
            keyword = "\\x" + re.sub(r"(?<=\w)(?=(?:\w\w)+$)", "\\x", keyword)
            process = subprocess.Popen(['grep', '-rlP', "^%s" % keyword, path], stdout=subprocess.PIPE)
        while process:
            if not self._running:
                process.kill()
                break
            fd = process.stdout.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            process_readline = str(process.stdout.readline())[2:-3]
            if not process_readline:
                if process.poll() != None: break
                continue
            search_additem = True
            if search_size == 2:
                filesize = os.path.getsize(process_readline)
                if filesize < size_sm or filesize > size_bg:
                    search_additem = False
            if search_time == 2:
                filetime = os.path.getmtime(process_readline)
                if filetime < time_sm or filetime > time_bg:
                    search_additem = False
            if search_additem:
                listView.insertItem(0, process_readline)
        msgbox.done(0)

class Tab3SearchThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, msgbox, path, search_type, search_format, search_size, size_sm, size_bg, search_time, time_sm, time_bg, listView):
        listView.clear()
        time.sleep(1)
        for root, dirs, files in os.walk(path):
            for filename in files:
                if not self._running: break
                filepath = "%s/%s" % (root, filename)
                filename_ext = os.path.splitext(filename.lower())[1][1:]
                search_additem = False
                if search_type == 1:
                    if filename_ext in image_format:
                        if search_format == 0:
                            search_additem = True
                        if search_format > 0:
                            if filename_ext == image_format[search_format - 1]:
                                search_additem = True
                if search_type == 2:
                    if filename_ext in audio_format:
                        if search_format == 0:
                            search_additem = True
                        if search_format > 0:
                            if filename_ext == audio_format[search_format - 1]:
                                search_additem = True
                if search_type == 3:
                    if filename_ext in video_format:
                        if search_format == 0:
                            search_additem = True
                        if search_format > 0:
                            if filename_ext == video_format[search_format - 1]:
                                search_additem = True
                if search_additem:
                    if search_size == 2:
                        filesize = os.path.getsize(filepath)
                        if filesize < size_sm or filesize > size_bg:
                            search_additem = False
                    if search_time == 2:
                        filetime = os.path.getmtime(filepath)
                        if filetime < time_sm or filetime > time_bg:
                            search_additem = False
                if search_additem:
                    listView.insertItem(0, '%s: %s' % (filename_ext.upper(), filepath) )
        msgbox.done(0)

class Tab4SearchThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def calcHash(self, im):
        try:
            im = Image.open(im)
            resize_width = 8
            resize_height = 8
            im = im.resize((resize_width, resize_height))
            im = im.convert('L')
            pixels = list(im.getdata())
            difference = []
            for row in range(resize_height):
                row_start_index = row * resize_width
                for col in range(resize_width - 1):
                    left_pixel_index = row_start_index + col
                    difference.append(pixels[left_pixel_index] > pixels[left_pixel_index + 1])
            decimal_value = 0
            hash_string = ""
            for index, value in enumerate(difference):
                if value:
                    decimal_value += value * (2 ** (index % 8))
                if index % 8 == 7:
                    hash_string += str(hex(decimal_value)[2:].rjust(2, "0"))
                    decimal_value = 0
            return hash_string
        except:
            pass
        return 0
 
    def calcHamming(self, h1, h2):
        difference = (int(h1, 16)) ^ (int(h2, 16))
        return bin(difference).count("1")

    def run(self, msgbox, path, search_pic, search_size, size_sm, size_bg, search_time, time_sm, time_bg, listView):
        listView.clear()
        time.sleep(1)
        source_hash = self.calcHash(search_pic)
        if source_hash == 0:
            msgbox.done(0)
            return
        for root, dirs, files in os.walk(path):
            for filename in files:
                if not self._running: break
                filepath = "%s/%s" % (root, filename)
                filename_ext = os.path.splitext(filename.lower())[1][1:]
                if search_size == 2:
                    filesize = os.path.getsize(filepath)
                    if filesize < size_sm or filesize > size_bg:
                        continue
                if search_time == 2:
                    filetime = os.path.getmtime(filepath)
                    if filetime < time_sm or filetime > time_bg:
                        continue
                if filename_ext in image_format:
                    target_hash = self.calcHash(filepath)
                    if target_hash == 0: continue
                    hamming_distance = self.calcHamming(target_hash, source_hash)
                    listView.insertItem(0, '%d: %s' % (hamming_distance, filepath) )
        listView.sortItems(0)
        msgbox.done(0)

class Tab5RecoverThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, msgbox, recover_file, recover_dir, option_indirect, option_corrupted, option_quick, recover_type, recover_format, listView):
        listView.clear()
        time.sleep(1)
        command_line = ['foremost']
        if option_indirect: command_line.append('-d')
        if option_corrupted: command_line.append('-a')
        if option_quick: command_line.append('-q')
        command_line.append('-v')
        if recover_type != 1 and len(recover_format) > 0:
            command_line.append('-t')
            command_line.append(recover_format)
        command_line.append('-i')
        command_line.append(recover_file)
        command_line.append('-o')
        command_line.append(recover_dir)
        process = subprocess.Popen(command_line, stdout=subprocess.PIPE)
        start_output = False
        while process:
            if not self._running:
                process.kill()
                break
            fd = process.stdout.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            process_readline = str(process.stdout.readline())[2:-3]
            if not process_readline:
                if process.poll() != None: break
                continue
            if not start_output and 'File Offset' in process_readline:
                start_output = True
                continue
            if start_output and 'Finish:' in process_readline:
                start_output = False
                continue
            if start_output and len(process_readline) > 5 and len(process_readline) < 64 and '\\t' in process_readline and 'foundat=' not in process_readline:
                listView.insertItem(0, process_readline.replace('\\t', '\t'))
            if 'ERROR' in process_readline:
                listView.insertItem(0, process_readline.replace('\\t', '\t'))
        msgbox.done(0)

class Tab6GPSThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def get_exif_data(self, filepath):
        try:
            image = Image.open(filepath)
            exif_data = {}
            info = image._getexif()
            if info:
                for tag, value in info.items():
                    decoded = TAGS.get(tag, tag)
                    if decoded == "GPSInfo":
                        gps_data = {}
                        for t in value:
                            sub_decoded = GPSTAGS.get(t, t)
                            gps_data[sub_decoded] = value[t]
                        exif_data[decoded] = gps_data
                    else:
                        exif_data[decoded] = value
            return exif_data
        except:
            pass
        return 0

    def convert_to_degrees(self, value):
        get_float = lambda x: float(x[0]) / float(x[1])
        d = get_float(value[0])
        m = get_float(value[1])
        s = get_float(value[2])
        return d + (m / 60.0) + (s / 3600.0)

    def get_lat_lon(self, exif_data):
        try:
            gps_latitude = exif_data["GPSInfo"]["GPSLatitude"]
            gps_latitude_ref = exif_data["GPSInfo"]["GPSLatitudeRef"]
            gps_longitude = exif_data["GPSInfo"]["GPSLongitude"]
            gps_longitude_ref = exif_data["GPSInfo"]["GPSLongitudeRef"]
            if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
                lat = self.convert_to_degrees(gps_latitude)
                if gps_latitude_ref != 'N': lat = 0 - lat
                lon = self.convert_to_degrees(gps_longitude)
                if gps_longitude_ref != 'E': lon = 0 - lon
                return lat, lon
        except:
            pass
        return 0

    def get_time(self, exif_data):
        try:
            dateTime = exif_data["DateTimeOriginal"]
            timeArray = time.strptime(dateTime, "%Y:%m:%d %H:%M:%S")
            timestamp = time.mktime(timeArray)
            return timestamp
        except:
            pass
        return 0

    def run(self, msgbox, path, listView, webView):
        listView.clear()
        time.sleep(1)
        for root, dirs, files in os.walk(path):
            for filename in files:
                if not self._running: break
                filepath = "%s/%s" % (root, filename)
                filename_ext = os.path.splitext(filename.lower())[1][1:]
                if filename_ext in image_format:
                    exif_data = self.get_exif_data(filepath)
                    if exif_data == 0: continue
                    lat_lon = self.get_lat_lon(exif_data)
                    if lat_lon == 0: continue
                    time_stamp = self.get_time(exif_data)
                    if time_stamp == 0: time_stamp = os.path.getmtime(filepath)
                    date_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_stamp))
                    listView.insertItem(0, '[%s][%f, %f] %s' % (date_time, lat_lon[0], lat_lon[1], filepath) )
                    map_data.append((time_stamp, lat_lon[0], lat_lon[1]))
        listView.sortItems(0)
        msgbox.done(0)

class Tab7SearchThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, msgbox, path, listView):
        listView.clear()
        time.sleep(1)
        for root, dirs, files in os.walk(path):
            for filename in files:
                if not self._running: break
                filepath = "%s/%s" % (root, filename)
                filename_ext = os.path.splitext(filename.lower())[1][1:]
                search_additem = False
                if filename_ext == "db":
                    listView.insertItem(0, '%s: %s' % (filename_ext.upper(), filepath) )
        msgbox.done(0)

class Tab7DecryptThread:
    def __init__(self):
        self._running = True

    def terminate(self):
        self._running = False

    def run(self, msgbox, encrypted_file, password, decrypted_file):
        time.sleep(1)
        process = subprocess.Popen(['python', 'desql.py', encrypted_file, password, decrypted_file], stdout=subprocess.PIPE)
        start_output = False
        while process:
            if not self._running:
                process.kill()
                break
            if process.poll() != None: break
        msgbox.done(0)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())