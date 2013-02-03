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

import os
from printrun.pronterface_widgets import *
from printrun import gviz
from printrun.xybuttons import XYButtons
from printrun.zbuttons import ZButtons
from printrun.graph import Graph

try:
    import wx
except:
    print _("WX is not installed. This program requires WX to run.")
    raise

global buttonSize
buttonSize = (70, 25)  # Define sizes for the buttons on top rows

__author__="soaring38"

#global functions
def make_button(parent, label, callback, tooltip, container = None, size = wx.DefaultSize, style = 0):
    button = wx.Button(parent, -1, label, style = style, size = size)
    button.Bind(wx.EVT_BUTTON, callback)
    button.SetToolTip(wx.ToolTip(tooltip))
    #if container:
    #    container.Add(button)
    return button

def make_sized_button(*args):
    return make_button(*args, size = buttonSize)

def make_autosize_button(*args):
    return make_button(*args, size = (-1, buttonSize[1]), style = wx.BU_EXACTFIT)
#end global functions

class StandardView(wx.Frame):
    
    #constructor
    def __init__( self, parent ):
	wx.Frame.__init__ ( self, parent, title = "Printer Interface", size = self.getwindowsize())
        
        # this list will contain all controls that should be only enabled
        # when we're connected to a printer
        self.printerControls = []
        
        #set specific view ui
        #self.SetIcon(wx.Icon(pixmapfile("P-face.ico"), wx.BITMAP_TYPE_ICO))
        
        #define cpbuttons
        self.cpbuttons = [
            SpecialButton(_("Motors off"), ("M84"), (250, 250, 250), None, 0, _("Switch all motors off")),
            SpecialButton(_("Check temp"), ("M105"), (225, 200, 200), (2, 5), (1, 1), _("Check current hotend temperature")),
            SpecialButton(_("Extrude"), ("extrude"), (225, 200, 200), (4, 0), (1, 2), _("Advance extruder by set length")),
            SpecialButton(_("Reverse"), ("reverse"), (225, 200, 200), (5, 0), (1, 2), _("Reverse extruder by set length")),
        ]
        
        #define custom buttons
        self.custombuttons = []
        
        #define dictionnary for button management
        self.btndict = {}
        
    #get the windows size depending the platform
    def getwindowsize(self):
        winsize = (800, 500)
        if os.name == "nt":
            winsize = (800, 530)
        return winsize
        
    def cbuttons_reload(self):
        allcbs = []
        ubs = self.uppersizer
        cs = self.centersizer
        #for item in ubs.GetChildren():
        #    if hasattr(item.GetWindow(),"custombutton"):
        #        allcbs += [(ubs, item.GetWindow())]
        for item in cs.GetChildren():
            if hasattr(item.GetWindow(),"custombutton"):
                allcbs += [(cs, item.GetWindow())]
        for sizer, button in allcbs:
            #sizer.Remove(button)
            button.Destroy()
        self.custombuttonbuttons = []
        newbuttonbuttonindex = len(self.custombuttons)
        while newbuttonbuttonindex>0 and self.custombuttons[newbuttonbuttonindex-1] is None:
            newbuttonbuttonindex -= 1
        while len(self.custombuttons) < 13:
            self.custombuttons.append(None)
        for i in xrange(len(self.custombuttons)):
            btndef = self.custombuttons[i]
            try:
                b = wx.Button(self.panel, -1, btndef.label, style = wx.BU_EXACTFIT)
                b.SetToolTip(wx.ToolTip(_("Execute command: ")+btndef.command))
                if btndef.background:
                    b.SetBackgroundColour(btndef.background)
                    rr, gg, bb = b.GetBackgroundColour().Get()
                    if 0.3*rr+0.59*gg+0.11*bb < 60:
                        b.SetForegroundColour("#ffffff")
            except:
                if i == newbuttonbuttonindex:
                    self.newbuttonbutton = b = wx.Button(self.panel, -1, "+", size = (19, 18), style = wx.BU_EXACTFIT)
                    #b.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                    b.SetForegroundColour("#4444ff")
                    b.SetToolTip(wx.ToolTip(_("click to add new custom button")))
                    b.Bind(wx.EVT_BUTTON, self.cbutton_edit)
                else:
                    b = wx.Button(self.panel,-1, ".", size = (1, 1))
                    #b = wx.StaticText(self.panel,-1, "", size = (72, 22), style = wx.ALIGN_CENTRE+wx.ST_NO_AUTORESIZE) #+wx.SIMPLE_BORDER
                    b.Disable()
                    #continue
            b.custombutton = i
            b.properties = btndef
            if btndef is not None:
                b.Bind(wx.EVT_BUTTON, self.procbutton)
                b.Bind(wx.EVT_MOUSE_EVENTS, self.editbutton)
            #else:
            #    b.Bind(wx.EVT_BUTTON, lambda e:e.Skip())
            self.custombuttonbuttons.append(b)
            #if i<4:
            #    ubs.Add(b)
            #else:
            cs.Add(b, pos = ((i)/4, (i)%4))
        self.mainsizer.Layout()
    
    def cbutton_edit(self, e, button = None):
        bedit = ButtonEdit(self)
        if button is not None:
            n = button.custombutton
            bedit.name.SetValue(button.properties.label)
            bedit.command.SetValue(button.properties.command)
            if button.properties.background:
                colour = button.properties.background
                if type(colour) not in (str, unicode):
                    #print type(colour)
                    if type(colour) == tuple and tuple(map(type, colour)) == (int, int, int):
                        colour = map(lambda x:x%256, colour)
                        colour = wx.Colour(*colour).GetAsString(wx.C2S_NAME|wx.C2S_HTML_SYNTAX)
                    else:
                        colour = wx.Colour(colour).GetAsString(wx.C2S_NAME|wx.C2S_HTML_SYNTAX)
                bedit.color.SetValue(colour)
        else:
            n = len(self.custombuttons)
            while n>0 and self.custombuttons[n-1] is None:
                n -= 1
        if bedit.ShowModal() == wx.ID_OK:
            if n == len(self.custombuttons):
                self.custombuttons+=[None]
            self.custombuttons[n]=SpecialButton(bedit.name.GetValue().strip(), bedit.command.GetValue().strip(), custom = True)
            if bedit.color.GetValue().strip()!="":
                self.custombuttons[n].background = bedit.color.GetValue()
            self.cbutton_save(n, self.custombuttons[n])
        bedit.Destroy()
        self.cbuttons_reload()
        
    def setbackgroundcolor(self, color):
        print("TODO: implement StandardView:setbackgroundcolor")
    
    def clearoutput(self):
        self.logbox.Clear()
        
    def setprintbuttonlabel(self, label):
        wx.CallAfter(self.printbtn.SetLabel, label)

    def setpausebuttonlabel(self, label):
        wx.CallAfter(self.pausebtn.SetLabel, label)
        
    def enablerecoverbutton(self, enable):
        if enable: wx.CallAfter(self.recoverbtn.Enable)
        else: wx.CallAfter(self.recoverbtn.Disable)
        
    def enablepausebutton(self, enable):
        if enable: wx.CallAfter(self.pausebtn.Enable)
        else: wx.CallAfter(self.pausebtn.Disable)
        
    def enableprintbutton(self, enable):
        if enable: wx.CallAfter(self.printbtn.Enable)
        else: wx.CallAfter(self.printbtn.Disable)
        
    def setstatustext(self, text):
        wx.CallAfter(self.status.SetStatusText, text)
        
    def serialportclear(self):
        self.serialport.Clear()
        
    def serialportappenditems(self, items):
        self.serialport.AppendItems(items)
        
    def serialportsetvalue(self, value):
        self.serialport.SetValue(value)
        
    def addtexttolog(self,text):
        try:
            self.logbox.AppendText(text)
        except:
            print "attempted to write invalid text to console"
            pass

        