#!/usr/bin/env python

# This file is part of the Printrun suite.
#
# Printrun is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Printrun is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Printrun.  If not, see <http://www.gnu.org/licenses/>.

import os, Queue, re

from printrun.printrun_utils import install_locale
install_locale('pronterface')

try:
    import wx
except:
    print _("WX is not installed. This program requires WX to run.")
    raise

import sys, glob, time, datetime, threading, traceback, cStringIO, subprocess
from printrun.pronterface_widgets import *
from printrun.printrun_utils import pixmapfile, configfile
from wx.lib.pubsub import Publisher as pub
import pronsole


StringIO = cStringIO

def dosify(name):
    return os.path.split(name)[1].split(".")[0][:8]+".g"


def parse_temperature_report(report, key):
    if key in report:
        return float(filter(lambda x: x.startswith(key), report.split())[0].split(":")[1].split("/")[0])
    else: 
        return -1.0


def format_time(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def format_duration(delta):
    return str(datetime.timedelta(seconds = int(delta)))


class Tee(object):
    def __init__(self, target):
        self.stdout = sys.stdout
        sys.stdout = self
        self.target = target
    def __del__(self):
        sys.stdout = self.stdout
    def write(self, data):
        try:
            self.target(data)
        except:
            pass
        self.stdout.write(data.encode("utf-8"))
    def flush(self):
        self.stdout.flush()


class PronterModel(pronsole.pronsole):
    def __init__(self, filename = None):
        
        #init the prconsole
        pronsole.pronsole.__init__(self)
        
        #init general settings
        self.settings.build_dimensions = '200x200x100+0+0+0' #default build dimensions are 200x200x100 with 0, 0, 0 in the corner of the bed
        self.settings.last_bed_temperature = 0.0
        self.settings.last_file_path = ""
        self.settings.last_temperature = 0.0
        self.settings.preview_extrusion_width = 0.5
        self.settings.preview_grid_step1 = 10.
        self.settings.preview_grid_step2 = 50.
        self.settings.bgcolor = "#FFFFFF"
        self.helpdict["build_dimensions"] = _("Dimensions of Build Platform\n & optional offset of origin\n\nExamples:\n   XXXxYYY\n   XXX,YYY,ZZZ\n   XXXxYYYxZZZ+OffX+OffY+OffZ")
        self.helpdict["last_bed_temperature"] = _("Last Set Temperature for the Heated Print Bed")
        self.helpdict["last_file_path"] = _("Folder of last opened file")
        self.helpdict["last_temperature"] = _("Last Temperature of the Hot End")
        self.helpdict["preview_extrusion_width"] = _("Width of Extrusion in Preview (default: 0.5)")
        self.helpdict["preview_grid_step1"] = _("Fine Grid Spacing (default: 10)")
        self.helpdict["preview_grid_step2"] = _("Coarse Grid Spacing (default: 50)")
        self.helpdict["bgcolor"] = _("Pronterface background color (default: #FFFFFF)")
        self.filename = filename
        os.putenv("UBUNTU_MENUPROXY", "0")
        self.statuscheck = False
        self.status_thread = None
        self.capture_skip = {}
        self.capture_skip_newline = False
        self.tempreport = ""
        self.monitor = 0
        self.f = None
        self.skeinp = None
        self.monitor_interval = 3
        self.paused = False
        self.sentlines = Queue.Queue(30)
        
        #parse commande line and load configuration
        self.parse_cmdline(sys.argv[1:])
        
        self.build_dimensions_list = self.get_build_dimensions(self.settings.build_dimensions)
        self.t = Tee(self.catchprint)
        self.stdout = sys.stdout
        self.skeining = 0
        self.mini = False
        self.p.sendcb = self.sentcb
        self.p.startcb = self.startcb
        self.p.endcb = self.endcb
        self.starttime = 0
        self.extra_print_time = 0
        self.curlayer = 0
        self.cur_button = None
        self.predisconnect_mainqueue = None
        self.predisconnect_queueindex = None
        self.predisconnect_layer = None
        self.hsetpoint = 0.0
        self.bsetpoint = 0.0
        self.webInterface = None
        if self.webrequested:
            try :
                import cherrypy
                from printrun import webinterface
                try:
                    self.webInterface = webinterface.WebInterface(self)
                    self.webThread = threading.Thread(target = webinterface.StartWebInterfaceThread, args = (self.webInterface, ))
                    self.webThread.start()
                except:
                    print _("Failed to start web interface")
                    traceback.print_exc(file = sys.stdout)
                    self.webInterface = None
            except:
                print _("CherryPy is not installed. Web Interface Disabled.")
        if self.filename is not None:
            self.do_load(self.filename)
              
    def get_build_dimensions(self, bdim):
        import re
        # a string containing up to six numbers delimited by almost anything
        # first 0-3 numbers specify the build volume, no sign, always positive
        # remaining 0-3 numbers specify the coordinates of the "southwest" corner of the build platform
        # "XXX,YYY"
        # "XXXxYYY+xxx-yyy"
        # "XXX,YYY,ZZZ+xxx+yyy-zzz"
        # etc
        bdl = re.match(
        "[^\d+-]*(\d+)?" + # X build size
        "[^\d+-]*(\d+)?" + # Y build size
        "[^\d+-]*(\d+)?" + # Z build size
        "[^\d+-]*([+-]\d+)?" + # X corner coordinate
        "[^\d+-]*([+-]\d+)?" + # Y corner coordinate
        "[^\d+-]*([+-]\d+)?"   # Z corner coordinate
        ,bdim).groups()
        defaults = [200, 200, 100, 0, 0, 0]
        bdl_float = [float(value) if value else defaults[i] for i, value in enumerate(bdl)]
        return bdl_float
    
    def catchprint(self, l):
        if self.capture_skip_newline and len(l) and not len(l.strip("\n\r")):
            self.capture_skip_newline = False
            return
        for pat in self.capture_skip.keys():
            if self.capture_skip[pat] > 0 and pat.match(l):
                self.capture_skip[pat] -= 1
                self.capture_skip_newline = True
                return
        pub.sendMessage("LOG_ADDTEXT", l)

    def sentcb(self, line):
        if "G1" in line:
            if "Z" in line:
                try:
                    layer = float(line.split("Z")[1].split()[0])
                    if layer != self.curlayer:
                        self.curlayer = layer
                        self.gviz.hilight = []
                        pub.sendMessage("SENTCB_START", None)
                except:
                    pass
            try:
                self.sentlines.put_nowait(line)
            except:
                pass
            #threading.Thread(target = self.gviz.addgcode, args = (line, 1)).start()
            #self.gwindow.p.addgcode(line, hilight = 1)
        if "M104" in line or "M109" in line:
            if "S" in line:
                try:
                    temp = float(line.split("S")[1].split("*")[0])
                    pub.sendMessage("SENTCB_SETEXTRUDER0TARGETTEMPERATURE", temp)
                except:
                    pass
            try:
                self.sentlines.put_nowait(line)
            except:
                pass
        if "M140" in line:
            if "S" in line:
                try:
                    temp = float(line.split("S")[1].split("*")[0])
                    pub.sendMessage("SENTCB_SETBEDTARGETTEMPERATURE", temp)
                except:
                    pass
            try:
                self.sentlines.put_nowait(line)
            except:
                pass
            
    def startcb(self):
        self.starttime = time.time()
        print "Print Started at: " + format_time(self.starttime)
    
    def endcb(self):
        if self.p.queueindex == 0:
            print "Print ended at: " + format_time(time.time())
            print_duration = int(time.time () - self.starttime + self.extra_print_time)
            print "and took: " + format_duration(print_duration)
            pub.sendMessage("ENDCB_DISABLEPAUSEBUTTON", None)
            pub.sendMessage("ENDCB_SETPRINTBUTTONLABEL", _("Print"))
                        
            param = self.settings.final_command
            if not param:
                return
            import shlex
            pararray = [i.replace("$s", str(self.filename)).replace("$t", format_duration(print_duration)).encode() for i in shlex.split(param.replace("\\", "\\\\").encode())]
            self.finalp = subprocess.Popen(pararray, stderr = subprocess.STDOUT, stdout = subprocess.PIPE)
    
    def project(self,event):
        from printrun import projectlayer
        if self.p.online:
            projectlayer.setframe(self,self.p).Show()
        else:
            print _("Printer is not online.")
            if self.webInterface:
                self.webInterface.AddLog("Printer is not online.")
                
    def setloud(self,e):
        self.p.loud=e.IsChecked()
        
    def rescanports(self, event = None):
        scan = self.scanserial()
        portslist = list(scan)
        if self.settings.port != "" and self.settings.port not in portslist:
            portslist += [self.settings.port]
            pub.sendMessage("SERIALPORT_CLEAR", None)
            pub.sendMessage("SERIALPORT_APPENDITEMS", portslist)
        try:
            if os.path.exists(self.settings.port) or self.settings.port in scan:
                pub.sendMessage("SERIALPORT_SETVALUE", self.settings.port)
            elif len(portslist) > 0:
                pub.sendMessage("SERIALPORT_SETVALUE", portslist[0])
        except:
            pass

    def scanserial(self):
        """scan for available ports. return a list of device names."""
        baselist = []
        if os.name == "nt":
            try:
                key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, "HARDWARE\\DEVICEMAP\\SERIALCOMM")
                i = 0
                while True:
                    baselist += [_winreg.EnumValue(key, i)[1]]
                    i += 1
            except:
                pass
        return baselist+glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob("/dev/tty.*") + glob.glob("/dev/cu.*") + glob.glob("/dev/rfcomm*")
    
    def sendline(self, e):
        command = self.commandbox.GetValue()
        if not len(command):
            return
        pub.sendMessage("LOG_ADDTEXT", ">>>" + command + "\n")
        self.onecmd(str(command))
        self.commandbox.SetSelection(0, len(command))
        self.commandbox.history+=[command]
        self.commandbox.histindex = len(self.commandbox.history)
