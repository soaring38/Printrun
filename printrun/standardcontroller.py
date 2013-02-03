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

#import pronterface
from prontermodel import PronterModel
from standardview import *
from printrun.pronterface_widgets import *
from printrun.graph import Graph
import threading
import pronsole
import os
from wx.lib.pubsub import Publisher as pub

try:
    import wx
except:
    print _("WX is not installed. This program requires WX to run.")
    raise

__author__="soaring38"

class StandardController:
    
    #constructor
    def __init__(self, app):
        
        #define the model
        self.model = PronterModel()
        
        #define the view
        self.view = StandardView(None)  
        
        #subscribe to model event
        self.subscribetomodel()
        
        #create display content
        self.popmenu()
        self.creategui()
        
        #display the window
        self.view.Show()
    
    def createxyzcontrolsizer(self):
        self.view.xyzcontent = wx.GridBagSizer()
        self.view.xyb = XYButtons(self.view.panel, self.moveXY, self.homebuttonclicked, self.spacebaraction, self.model.settings.bgcolor)
        self.view.xyzcontent.Add(self.view.xyb, pos = (0, 1), flag = wx.ALIGN_CENTER)
        self.view.zb = ZButtons(self.view.panel, self.moveZ, self.model.settings.bgcolor)
        self.view.xyzcontent.Add(self.view.zb, pos = (0, 2), flag = wx.ALIGN_CENTER)
        return self.view.xyzcontent
        #wx.CallAfter(self.view.xyb.SetFocus)
        
    def createleftpane(self):
        self.view.leftpane = wx.GridBagSizer()
        llts = wx.BoxSizer(wx.HORIZONTAL)
        self.view.leftpane.Add(llts, pos = (0, 0), span = (1, 9))
        self.view.xyzsizer = self.createxyzcontrolsizer()
        self.view.leftpane.Add(self.view.xyzsizer, pos = (1, 0), span = (1, 8), flag = wx.ALIGN_CENTER)
        
        for i in self.view.cpbuttons:
            btn = make_button(self.view.panel, i.label, self.procbutton, i.tooltip, style = wx.BU_EXACTFIT)
            btn.SetBackgroundColour(i.background)
            btn.SetForegroundColour("black")
            btn.properties = i
            self.view.btndict[i.command] = btn
            self.view.printerControls.append(btn)
            if i.pos == None:
                if i.span == 0:
                    llts.Add(btn)
            else:
                self.view.leftpane.Add(btn, pos = i.pos, span = i.span)

        self.view.xyfeedc = wx.SpinCtrl(self.view.panel,-1, str(self.model.settings.xy_feedrate), min = 0, max = 50000, size = (70,-1))
        self.view.xyfeedc.SetToolTip(wx.ToolTip("Set Maximum Speed for X & Y axes (mm/min)"))
        llts.Add(wx.StaticText(self.view.panel,-1, _("XY:")), flag = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
        llts.Add(self.view.xyfeedc)
        llts.Add(wx.StaticText(self.view.panel,-1, _("mm/min   Z:")), flag = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL)
        self.view.zfeedc = wx.SpinCtrl(self.view.panel,-1, str(self.model.settings.z_feedrate), min = 0, max = 50000, size = (70,-1))
        self.view.zfeedc.SetToolTip(wx.ToolTip("Set Maximum Speed for Z axis (mm/min)"))
        llts.Add(self.view.zfeedc,)

        self.view.monitorbox = wx.CheckBox(self.view.panel,-1, _("Watch"))
        self.view.monitorbox.SetToolTip(wx.ToolTip("Monitor Temperatures in Graph"))
        self.view.leftpane.Add(self.view.monitorbox, pos = (2, 6))
        self.view.monitorbox.Bind(wx.EVT_CHECKBOX, self.setmonitor)

        self.view.leftpane.Add(wx.StaticText(self.view.panel,-1, _("Heat:")), pos = (2, 0), span = (1, 1), flag = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT)
        htemp_choices = [self.model.temps[i]+" ("+i+")" for i in sorted(self.model.temps.keys(), key = lambda x:self.model.temps[x])]

        self.view.settoff = make_button(self.view.panel, _("Off"), lambda e: self.do_settemp("off"), _("Switch Hotend Off"), size = (36,-1), style = wx.BU_EXACTFIT)
        self.view.printerControls.append(self.view.settoff)
        self.view.leftpane.Add(self.view.settoff, pos = (2, 1), span = (1, 1))

        if self.model.settings.last_temperature not in map(float, self.model.temps.values()):
            htemp_choices = [str(self.model.settings.last_temperature)] + htemp_choices
        self.view.htemp = wx.ComboBox(self.view.panel, -1,
                choices = htemp_choices, style = wx.CB_DROPDOWN, size = (70,-1))
        self.view.htemp.SetToolTip(wx.ToolTip("Select Temperature for Hotend"))
        self.view.htemp.Bind(wx.EVT_COMBOBOX, self.htemp_change)

        self.view.leftpane.Add(self.view.htemp, pos = (2, 2), span = (1, 2))
        self.view.settbtn = make_button(self.view.panel, _("Set"), self.do_settemp, _("Switch Hotend On"), size = (38, -1), style = wx.BU_EXACTFIT)
        self.view.printerControls.append(self.view.settbtn)
        self.view.leftpane.Add(self.view.settbtn, pos = (2, 4), span = (1, 1))

        self.view.leftpane.Add(wx.StaticText(self.view.panel,-1, _("Bed:")), pos = (3, 0), span = (1, 1), flag = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT)
        btemp_choices = [self.model.bedtemps[i]+" ("+i+")" for i in sorted(self.model.bedtemps.keys(), key = lambda x:self.model.temps[x])]

        self.view.setboff = make_button(self.view.panel, _("Off"), lambda e:self.do_bedtemp("off"), _("Switch Heated Bed Off"), size = (36,-1), style = wx.BU_EXACTFIT)
        self.view.printerControls.append(self.view.setboff)
        self.view.leftpane.Add(self.view.setboff, pos = (3, 1), span = (1, 1))

        if self.model.settings.last_bed_temperature not in map(float, self.model.bedtemps.values()):
            btemp_choices = [str(self.model.settings.last_bed_temperature)] + btemp_choices
        self.view.btemp = wx.ComboBox(self.view.panel, -1,
                choices = btemp_choices, style = wx.CB_DROPDOWN, size = (70,-1))
        self.view.btemp.SetToolTip(wx.ToolTip("Select Temperature for Heated Bed"))
        self.view.btemp.Bind(wx.EVT_COMBOBOX, self.btemp_change)
        self.view.leftpane.Add(self.view.btemp, pos = (3, 2), span = (1, 2))

        self.view.setbbtn = make_button(self.view.panel, _("Set"), self.do_bedtemp, ("Switch Heated Bed On"), size = (38, -1), style = wx.BU_EXACTFIT)
        self.view.printerControls.append(self.view.setbbtn)
        self.view.leftpane.Add(self.view.setbbtn, pos = (3, 4), span = (1, 1))

        self.view.btemp.SetValue(str(self.model.settings.last_bed_temperature))
        self.view.htemp.SetValue(str(self.model.settings.last_temperature))

        ## added for an error where only the bed would get (pla) or (abs).
        #This ensures, if last temp is a default pla or abs, it will be marked so.
        # if it is not, then a (user) remark is added. This denotes a manual entry

        for i in btemp_choices:
            if i.split()[0] == str(self.model.settings.last_bed_temperature).split('.')[0] or i.split()[0] == str(self.model.settings.last_bed_temperature):
                self.view.btemp.SetValue(i)
        for i in htemp_choices:
            if i.split()[0] == str(self.model.settings.last_temperature).split('.')[0] or i.split()[0] == str(self.model.settings.last_temperature) :
                self.view.htemp.SetValue(i)

        if( '(' not in self.view.btemp.Value):
            self.view.btemp.SetValue(self.view.btemp.Value + ' (user)')
        if( '(' not in self.view.htemp.Value):
            self.view.htemp.SetValue(self.view.htemp.Value + ' (user)')

        self.view.tempdisp = wx.StaticText(self.view.panel,-1, "")

        self.view.edist = wx.SpinCtrl(self.view.panel,-1, "5", min = 0, max = 1000, size = (60,-1))
        self.view.edist.SetBackgroundColour((225, 200, 200))
        self.view.edist.SetForegroundColour("black")
        self.view.leftpane.Add(self.view.edist, pos = (4, 2), span = (1, 2))
        self.view.leftpane.Add(wx.StaticText(self.view.panel,-1, _("mm")), pos = (4, 4), span = (1, 1))
        self.view.edist.SetToolTip(wx.ToolTip("Amount to Extrude or Retract (mm)"))
        self.view.efeedc = wx.SpinCtrl(self.view.panel,-1, str(self.model.settings.e_feedrate), min = 0, max = 50000, size = (60,-1))
        self.view.efeedc.SetToolTip(wx.ToolTip("Extrude / Retract speed (mm/min)"))
        self.view.efeedc.SetBackgroundColour((225, 200, 200))
        self.view.efeedc.SetForegroundColour("black")
        self.view.efeedc.Bind(wx.EVT_SPINCTRL, self.setfeeds)
        self.view.leftpane.Add(self.view.efeedc, pos = (5, 2), span = (1, 2))
        self.view.leftpane.Add(wx.StaticText(self.view.panel,-1, _("mm/\nmin")), pos = (5, 4), span = (1, 1))
        self.view.xyfeedc.Bind(wx.EVT_SPINCTRL, self.setfeeds)
        self.view.zfeedc.Bind(wx.EVT_SPINCTRL, self.setfeeds)
        self.view.zfeedc.SetBackgroundColour((180, 255, 180))
        self.view.zfeedc.SetForegroundColour("black")

        self.view.graph = Graph(self.view.panel, wx.ID_ANY)
        self.view.leftpane.Add(self.view.graph, pos = (3, 5), span = (3, 3))
        self.view.leftpane.Add(self.view.tempdisp, pos = (6, 0), span = (1, 9))
    
        return self.view.leftpane
    
    def createvizpane(self):
        self.view.vizpane = wx.BoxSizer(wx.VERTICAL)
        
        self.view.gviz = gviz.gviz(self.view.panel, (300, 300),
        build_dimensions = self.model.build_dimensions_list,
        grid = (self.model.settings.preview_grid_step1, self.model.settings.preview_grid_step2),
        extrusion_width = self.model.settings.preview_extrusion_width)
        self.view.gviz.SetToolTip(wx.ToolTip("Click to examine / edit\n  layers of loaded file"))
        self.view.gviz.showall = 1
        try:
            raise ""
            import printrun.stlview
            self.view.gwindow = printrun.stlview.GCFrame(None, wx.ID_ANY, 'Gcode view, shift to move view, mousewheel to set layer', size = (600, 600))
        except:
            self.view.gwindow = gviz.window([],
            build_dimensions = self.model.build_dimensions_list,
            grid = (self.model.settings.preview_grid_step1, self.model.settings.preview_grid_step2),
            extrusion_width = self.model.settings.preview_extrusion_width)
        self.view.gviz.Bind(wx.EVT_LEFT_DOWN, self.showwin)
        self.view.gwindow.Bind(wx.EVT_CLOSE, lambda x:self.view.gwindow.Hide())
        self.view.vizpane.Add(self.view.gviz, 1, flag = wx.SHAPED)
        cs = self.view.centersizer = wx.GridBagSizer()
        self.view.vizpane.Add(cs, 0, flag = wx.EXPAND)
    
        return self.view.vizpane
    
    def createmaintoolbar(self):
        
        content = wx.BoxSizer(wx.HORIZONTAL)
        self.view.rescanbtn = make_sized_button(self.view.panel, _("Port"), self.rescanports, _("Communication Settings\nClick to rescan ports"))
        content.Add(self.view.rescanbtn, 0, wx.TOP|wx.LEFT, 0)

        self.view.serialport = wx.ComboBox(self.view.panel, -1,
                choices = self.model.scanserial(),
                style = wx.CB_DROPDOWN, size = (150, 25))
        self.view.serialport.SetToolTip(wx.ToolTip("Select Port Printer is connected to"))
        self.model.rescanports()
        content.Add(self.view.serialport)

        content.Add(wx.StaticText(self.view.panel,-1, "@"), 0, wx.RIGHT|wx.ALIGN_CENTER, 0)
        self.view.baud = wx.ComboBox(self.view.panel, -1,
                choices = ["2400", "9600", "19200", "38400", "57600", "115200", "250000"],
                style = wx.CB_DROPDOWN,  size = (100, 25))
        self.view.baud.SetToolTip(wx.ToolTip("Select Baud rate for printer communication"))
        try:
            self.view.baud.SetValue("115200")
            self.view.baud.SetValue(str(self.model.settings.baudrate))
        except:
            pass
        content.Add(self.view.baud)
        
        self.view.connectbtn = make_sized_button(self.view.panel, _("Connect"), self.connect, _("Connect to the printer"), self)

        self.view.resetbtn = make_autosize_button(self.view.panel, _("Reset"), self.reset, _("Reset the printer"), self)
        self.view.loadbtn = make_autosize_button(self.view.panel, _("Load file"), self.loadfile, _("Load a 3D model file"), self)
        self.view.platebtn = make_autosize_button(self.view.panel, _("Compose"), self.plate, _("Simple Plater System"), self)
        self.view.sdbtn = make_autosize_button(self.view.panel, _("SD"), self.sdmenu, _("SD Card Printing"), self)
        self.view.printerControls.append(self.view.sdbtn)
        self.view.printbtn = make_sized_button(self.view.panel, _("Print"), self.printfile, _("Start Printing Loaded File"), self)
        self.view.enableprintbutton(False)
        self.view.pausebtn = make_sized_button(self.view.panel, _("Pause"), self.pause, _("Pause Current Print"), self)
        self.view.recoverbtn = make_sized_button(self.view.panel, _("Recover"), self.recover, _("Recover previous Print"), self)
        
        return content
    
    def createlogpane(self):

        content = wx.BoxSizer(wx.VERTICAL)
        #root.lowerrsizer = self
        self.view.logbox = wx.TextCtrl(self.view.panel, style = wx.TE_MULTILINE, size = (350,-1))
        self.view.logbox.SetEditable(0)
        content.Add(self.view.logbox, 1, wx.EXPAND)
        lbrs = wx.BoxSizer(wx.HORIZONTAL)
        self.view.commandbox = wx.TextCtrl(self.view.panel, style = wx.TE_PROCESS_ENTER)
        self.view.commandbox.SetToolTip(wx.ToolTip("Send commands to printer\n(Type 'help' for simple\nhelp function)"))
        self.view.commandbox.Bind(wx.EVT_TEXT_ENTER, self.sendline)
        self.view.commandbox.Bind(wx.EVT_CHAR, self.cbkey)
        self.view.commandbox.history = [u""]
        self.view.commandbox.histindex = 1
        #root.printerControls.append(root.commandbox)
        lbrs.Add(self.view.commandbox, 1)
        self.view.sendbtn = make_button(self.view.panel, _("Send"), self.sendline, _("Send Command to Printer"), style = wx.BU_EXACTFIT, container = lbrs)
        #root.printerControls.append(root.sendbtn)
        content.Add(lbrs, 0, wx.EXPAND)
        return content
        
    def creategui(self) :
        self.view.setbackgroundcolor(self.model.settings.bgcolor)
        self.view.panel = wx.Panel(self.view,-1, size = self.view.getwindowsize())
        self.view.uppersizer = self.createmaintoolbar()
        self.view.mainsizer = wx.BoxSizer(wx.VERTICAL)
        self.view.lowersizer = wx.BoxSizer(wx.HORIZONTAL)
        self.view.lowersizer.Add(self.createleftpane())
        self.view.lowersizer.Add(self.createvizpane(), 1, wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL)
        self.view.lowersizer.Add(self.createlogpane(), 0, wx.EXPAND)
        self.view.mainsizer.Add(self.view.uppersizer)
        self.view.mainsizer.Add(self.view.lowersizer, 1, wx.EXPAND)
        self.view.panel.SetSizer(self.view.mainsizer)
        self.view.status = self.view.CreateStatusBar()
        self.view.status.SetStatusText(_("Not connected to printer."))
        self.view.mainsizer.Layout()
        self.view.mainsizer.Fit(self.view)
        
        #binding
        self.view.panel.Bind(wx.EVT_MOUSE_EVENTS, self.editbutton)
        self.view.Bind(wx.EVT_CLOSE, self.kill)
        
        # disable all printer controls until we connect to a printer
        self.view.enablepausebutton(False)
        self.view.enablerecoverbutton(False)

        for i in self.view.printerControls:
            i.Disable()

        self.view.cbuttons_reload()
        
    def popmenu(self):
        self.view.menustrip = wx.MenuBar()
        
        # File menu
        m = wx.Menu()
        self.view.Bind(wx.EVT_MENU, self.loadfile, m.Append(-1, _("&Open..."), _(" Opens file")))
        self.view.Bind(wx.EVT_MENU, self.do_editgcode, m.Append(-1, _("&Edit..."), _(" Edit open file")))
        self.view.Bind(wx.EVT_MENU, self.clearoutput, m.Append(-1, _("Clear console"), _(" Clear output console")))
        self.view.Bind(wx.EVT_MENU, self.project, m.Append(-1, _("Projector"), _(" Project slices")))
        self.view.Bind(wx.EVT_MENU, self.OnExit, m.Append(wx.ID_EXIT, _("E&xit"), _(" Closes the Window")))
        self.view.menustrip.Append(m, _("&File"))
        
        # Settings menu
        m = wx.Menu()
        self.view.macros_menu = wx.Menu()
        m.AppendSubMenu(self.view.macros_menu, _("&Macros"))
        
        self.view.Bind(wx.EVT_MENU, self.new_macro, self.view.macros_menu.Append(-1, _("<&New...>")))
        self.view.Bind(wx.EVT_MENU, lambda *e:options(self.model), m.Append(-1, _("&Options"), _(" Options dialog")))
        self.view.Bind(wx.EVT_MENU, lambda x: threading.Thread(target = lambda:self.do_skein("set")).start(), m.Append(-1, _("Slicing Settings"), _(" Adjust slicing settings")))

        mItem = m.AppendCheckItem(-1, _("Debug G-code"), _("Print all G-code sent to and received from the printer."))
        m.Check(mItem.GetId(), self.model.p.loud)
        self.view.Bind(wx.EVT_MENU, self.setloud, mItem)

        self.view.menustrip.Append(m, _("&Settings"))
        self.update_macros_menu()
        self.view.SetMenuBar(self.view.menustrip)
    
    def update_macros_menu(self):
        if not hasattr(self.view, "macros_menu"):
            return # too early, menu not yet built
        try:
            while True:
                item = self.view.macros_menu.FindItemByPosition(1)
                if item is None: return
                self.view.macros_menu.DeleteItem(item)
        except:
            pass
        for macro in self.model.macros.keys():
            self.Bind(wx.EVT_MENU, lambda x, m = macro: self.model.start_macro(m, self.model.macros[m]), self.view.macros_menu.Append(-1, macro))
    
    def OnExit(self, evt):
        self.view.Close()
        
    def do_editgcode(self, e = None):
        if self.model.filename is not None:
            MacroEditor(self.model.filename, self.model.f, self.doneediting, 1)
        
    def loadfile(self, event, filename = None):
        if self.model.skeining and self.model.skeinp is not None:
            self.model.skeinp.terminate()
            return
        basedir = self.model.settings.last_file_path
        if not os.path.exists(basedir):
            basedir = "."
            try:
                basedir = os.path.split(self.filename)[0]
            except:
                pass
        dlg = wx.FileDialog(self.view, _("Open file to print"), basedir, style = wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
        dlg.SetWildcard(_("OBJ, STL, and GCODE files (*.gcode;*.gco;*.g;*.stl;*.STL;*.obj;*.OBJ)|*.gcode;*.gco;*.g;*.stl;*.STL;*.obj;*.OBJ|All Files (*.*)|*.*"))
        if(filename is not None or dlg.ShowModal() == wx.ID_OK):
            if filename is not None:
                name = filename
            else:
                name = dlg.GetPath()
            if not(os.path.exists(name)):
                self.model.status.SetStatusText(_("File not found!"))
                return
            path = os.path.split(name)[0]
            if path != self.model.settings.last_file_path:
                self.model.set("last_file_path", path)
            if name.lower().endswith(".stl"):
                self.model.skein(name)
            elif name.lower().endswith(".obj"):
                self.model.skein(name)
            else:
                self.model.filename = name
                of = open(self.model.filename)
                self.model.f = [i.replace("\n", "").replace("\r", "") for i in of]
                of.close()
                self.view.setstatustext(_("Loaded %s, %d lines") % (name, len(self.model.f)))
                self.view.setprintbuttonlabel(_("Print"))
                self.view.setpausebuttonlabel(_("Pause"))
                self.view.enablepausebutton(False)
                self.view.enablerecoverbutton(False)
                
                if self.model.p.online:
                    self.view.enableprintbutton(True)
                threading.Thread(target = self.loadviz).start()
    
    def new_macro(self, e = None):
        dialog = wx.Dialog(self.view, -1, _("Enter macro name"), size = (260, 85))
        panel = wx.Panel(dialog, -1)
        vbox = wx.BoxSizer(wx.VERTICAL)
        wx.StaticText(panel, -1, _("Macro name:"), (8, 14))
        dialog.namectrl = wx.TextCtrl(panel, -1, '', (110, 8), size = (130, 24), style = wx.TE_PROCESS_ENTER)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        okb = wx.Button(dialog, wx.ID_OK, _("Ok"), size = (60, 24))
        dialog.Bind(wx.EVT_TEXT_ENTER, lambda e:dialog.EndModal(wx.ID_OK), dialog.namectrl)
        #dialog.Bind(wx.EVT_BUTTON, lambda e:self.new_macro_named(dialog, e), okb)
        hbox.Add(okb)
        hbox.Add(wx.Button(dialog, wx.ID_CANCEL, _("Cancel"), size = (60, 24)))
        vbox.Add(panel)
        vbox.Add(hbox, 1, wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, 10)
        dialog.SetSizer(vbox)
        dialog.Centre()
        macro = ""
        if dialog.ShowModal() == wx.ID_OK:
            macro = dialog.namectrl.GetValue()
            if macro != "":
                wx.CallAfter(self.edit_macro, macro)
        dialog.Destroy()
        return macro
    
    def edit_macro(self, macro):
        if macro == "": return self.new_macro()
        if self.model.macros.has_key(macro):
            old_def = self.model.macros[macro]
        elif len([c for c in macro.encode("ascii", "replace") if not c.isalnum() and c != "_"]):
            print _("Macro name may contain only ASCII alphanumeric symbols and underscores")
            if self.model.webInterface:
                self.model.webInterface.AddLog("Macro name may contain only alphanumeric symbols and underscores")
            return
        elif hasattr(self.model.__class__, "do_"+macro):
            print _("Name '%s' is being used by built-in command") % macro
            return
        else:
            old_def = ""
        self.model.start_macro(macro, old_def)
        return macro
    
    def kill(self, e):
        self.model.statuscheck = False
        if self.model.status_thread:
            self.model.status_thread.join()
            self.model.status_thread = None
        self.model.p.recvcb = None
        self.model.p.disconnect()
        if hasattr(self.model, "feedrates_changed"):
            self.model.save_in_rc("set xy_feedrate", "set xy_feedrate %d" % self.settings.xy_feedrate)
            self.model.save_in_rc("set z_feedrate", "set z_feedrate %d" % self.settings.z_feedrate)
            self.model.save_in_rc("set e_feedrate", "set e_feedrate %d" % self.settings.e_feedrate)
        try:
            self.view.gwindow.Destroy()
        except:
            pass
        self.view.Destroy()
        if self.model.webInterface:
            from printrun import webinterface
            webinterface.KillWebInterfaceThread()
    
    def editbutton(self, e):
        if e.IsCommandEvent() or e.ButtonUp(wx.MOUSE_BTN_RIGHT):
            if e.IsCommandEvent():
                pos = (0, 0)
            else:
                pos = e.GetPosition()
            popupmenu = wx.Menu()
            obj = e.GetEventObject()
            if hasattr(obj, "custombutton"):
                item = popupmenu.Append(-1, _("Edit custom button '%s'") % e.GetEventObject().GetLabelText())
                self.view.Bind(wx.EVT_MENU, lambda e, button = e.GetEventObject():self.cbutton_edit(e, button), item)
                item = popupmenu.Append(-1, _("Move left <<"))
                self.view.Bind(wx.EVT_MENU, lambda e, button = e.GetEventObject():self.cbutton_order(e, button,-1), item)
                if obj.custombutton == 0: item.Enable(False)
                item = popupmenu.Append(-1, _("Move right >>"))
                self.view.Bind(wx.EVT_MENU, lambda e, button = e.GetEventObject():self.cbutton_order(e, button, 1), item)
                if obj.custombutton == 63: item.Enable(False)
                pos = self.view.panel.ScreenToClient(e.GetEventObject().ClientToScreen(pos))
                item = popupmenu.Append(-1, _("Remove custom button '%s'") % e.GetEventObject().GetLabelText())
                self.view.Bind(wx.EVT_MENU, lambda e, button = e.GetEventObject():self.cbutton_remove(e, button), item)
            else:
                item = popupmenu.Append(-1, _("Add custom button"))
                self.view.Bind(wx.EVT_MENU, self.cbutton_edit, item)
            self.view.panel.PopupMenu(popupmenu, pos)
        elif e.Dragging() and e.ButtonIsDown(wx.MOUSE_BTN_LEFT):
            obj = e.GetEventObject()
            scrpos = obj.ClientToScreen(e.GetPosition())
            if not hasattr(self.view, "dragpos"):
                self.view.dragpos = scrpos
                e.Skip()
                return
            else:
                dx, dy = self.view.dragpos[0]-scrpos[0], self.view.dragpos[1]-scrpos[1]
                if dx*dx+dy*dy < 5*5: # threshold to detect dragging for jittery mice
                    e.Skip()
                    return
            if not hasattr(self.view, "dragging"):
                # init dragging of the custom button
                if hasattr(obj, "custombutton") and obj.properties is not None:
                    #self.newbuttonbutton.SetLabel("")
                    #self.newbuttonbutton.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                    #self.newbuttonbutton.SetForegroundColour("black")
                    #self.newbuttonbutton.SetSize(obj.GetSize())
                    #if self.uppersizer.GetItem(self.newbuttonbutton) is not None:
                    #    self.uppersizer.SetItemMinSize(self.newbuttonbutton, obj.GetSize())
                    #    self.mainsizer.Layout()
                    for b in self.view.custombuttonbuttons:
                        #if b.IsFrozen(): b.Thaw()
                        if b.properties is None:
                            b.Enable()
                            b.SetLabel("")
                            b.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                            b.SetForegroundColour("black")
                            b.SetSize(obj.GetSize())
                            if self.view.uppersizer.GetItem(b) is not None:
                                self.view.uppersizer.SetItemMinSize(b, obj.GetSize())
                                self.view.mainsizer.Layout()
                        #    b.SetStyle(wx.ALIGN_CENTRE+wx.ST_NO_AUTORESIZE+wx.SIMPLE_BORDER)
                    self.view.dragging = wx.Button(self.view.panel,-1, obj.GetLabel(), style = wx.BU_EXACTFIT)
                    self.view.dragging.SetBackgroundColour(obj.GetBackgroundColour())
                    self.view.dragging.SetForegroundColour(obj.GetForegroundColour())
                    self.view.dragging.sourcebutton = obj
                    self.view.dragging.Raise()
                    self.view.dragging.Disable()
                    self.view.dragging.SetPosition(self.view.panel.ScreenToClient(scrpos))
                    self.view.last_drag_dest = obj
                    self.view.dragging.label = obj.s_label = obj.GetLabel()
                    self.view.dragging.bgc = obj.s_bgc = obj.GetBackgroundColour()
                    self.view.dragging.fgc = obj.s_fgc = obj.GetForegroundColour()
            else:
                # dragging in progress
                self.view.dragging.SetPosition(self.view.panel.ScreenToClient(scrpos))
                wx.CallAfter(self.view.dragging.Refresh)
                btns = self.view.custombuttonbuttons
                dst = None
                src = self.view.dragging.sourcebutton
                drg = self.view.dragging
                for b in self.view.custombuttonbuttons:
                    if b.GetScreenRect().Contains(scrpos):
                        dst = b
                        break
                #if dst is None and self.panel.GetScreenRect().Contains(scrpos):
                #    # try to check if it is after buttons at the end
                #    tspos = self.panel.ClientToScreen(self.uppersizer.GetPosition())
                #    bspos = self.panel.ClientToScreen(self.centersizer.GetPosition())
                #    tsrect = wx.Rect(*(tspos.Get()+self.uppersizer.GetSize().Get()))
                #    bsrect = wx.Rect(*(bspos.Get()+self.centersizer.GetSize().Get()))
                #    lbrect = btns[-1].GetScreenRect()
                #    p = scrpos.Get()
                #    if len(btns)<4 and tsrect.Contains(scrpos):
                #        if lbrect.GetRight() < p[0]:
                #            print "Right of last button on upper cb sizer"
                #    if bsrect.Contains(scrpos):
                #        if lbrect.GetBottom() < p[1]:
                #            print "Below last button on lower cb sizer"
                #        if lbrect.GetRight() < p[0] and lbrect.GetTop() <= p[1] and lbrect.GetBottom() >= p[1]:
                #            print "Right to last button on lower cb sizer"
                if dst is not self.view.last_drag_dest:
                    if self.view.last_drag_dest is not None:
                        self.view.last_drag_dest.SetBackgroundColour(self.view.last_drag_dest.s_bgc)
                        self.view.last_drag_dest.SetForegroundColour(self.view.last_drag_dest.s_fgc)
                        self.view.last_drag_dest.SetLabel(self.view.last_drag_dest.s_label)
                    if dst is not None and dst is not src:
                        dst.s_bgc = dst.GetBackgroundColour()
                        dst.s_fgc = dst.GetForegroundColour()
                        dst.s_label = dst.GetLabel()
                        src.SetBackgroundColour(dst.GetBackgroundColour())
                        src.SetForegroundColour(dst.GetForegroundColour())
                        src.SetLabel(dst.GetLabel())
                        dst.SetBackgroundColour(drg.bgc)
                        dst.SetForegroundColour(drg.fgc)
                        dst.SetLabel(drg.label)
                    else:
                        src.SetBackgroundColour(drg.bgc)
                        src.SetForegroundColour(drg.fgc)
                        src.SetLabel(drg.label)
                    self.view.last_drag_dest = dst
        elif hasattr(self.view, "dragging") and not e.ButtonIsDown(wx.MOUSE_BTN_LEFT):
            # dragging finished
            obj = e.GetEventObject()
            scrpos = obj.ClientToScreen(e.GetPosition())
            dst = None
            src = self.view.dragging.sourcebutton
            drg = self.view.dragging
            for b in self.view.custombuttonbuttons:
                if b.GetScreenRect().Contains(scrpos):
                    dst = b
                    break
            if dst is not None:
                src_i = src.custombutton
                dst_i = dst.custombutton
                self.view.custombuttons[src_i], self.view.custombuttons[dst_i] = self.view.custombuttons[dst_i], self.view.custombuttons[src_i]
                self.cbutton_save(src_i, self.view.custombuttons[src_i])
                self.cbutton_save(dst_i, self.view.custombuttons[dst_i])
                while self.view.custombuttons[-1] is None:
                    del self.view.custombuttons[-1]
            wx.CallAfter(self.view.dragging.Destroy)
            del self.view.dragging
            wx.CallAfter(self.view.cbuttons_reload)
            del self.view.last_drag_dest
            del self.view.dragpos
        else:
            e.Skip()
            
    def cbutton_save(self, n, bdef, new_n = None):
        if new_n is None: new_n = n
        if bdef is None or bdef == "":
            self.model.save_in_rc(("button %d" % n),'')
        elif bdef.background:
            colour = bdef.background
            if type(colour) not in (str, unicode):
                #print type(colour), map(type, colour)
                if type(colour) == tuple and tuple(map(type, colour)) == (int, int, int):
                    colour = map(lambda x:x%256, colour)
                    colour = wx.Colour(*colour).GetAsString(wx.C2S_NAME|wx.C2S_HTML_SYNTAX)
                else:
                    colour = wx.Colour(colour).GetAsString(wx.C2S_NAME|wx.C2S_HTML_SYNTAX)
            self.model.save_in_rc(("button %d" % n),'button %d "%s" /c "%s" %s' % (new_n, bdef.label, colour, bdef.command))
        else:
            self.model.save_in_rc(("button %d" % n),'button %d "%s" %s' % (new_n, bdef.label, bdef.command))
     
    def procbutton(self, e):
        try:
            if hasattr(e.GetEventObject(),"custombutton"):
                if wx.GetKeyState(wx.WXK_CONTROL) or wx.GetKeyState(wx.WXK_ALT):
                    return self.editbutton(e)
                self.view.cur_button = e.GetEventObject().custombutton
            self.model.onecmd(e.GetEventObject().properties.command)
            self.view.cur_button = None
        except:
            print _("event object missing")
            if self.model.webInterface:
                self.model.webInterface.AddLog("event object missing")
            self.view.cur_button = None
            raise
    
    def moveXY(self, x, y):
        if x != 0:
            self.model.onecmd('move X %s' % x)
        if y != 0:
            self.model.onecmd('move Y %s' % y)
        # When user clicks on the XY control, the Z control no longer gets spacebar/repeat signals
        self.view.zb.clearRepeat()
        
    def loadcustombuttonsconfiguration(self):
        #try to read and load custom buttons configuration
            customdict = {}
            try:
                execfile(configfile("custombtn.txt"), customdict)
                if len(customdict["btns"]):
                    if not len(self.view.custombuttons):
                        try:
                            self.view.custombuttons = customdict["btns"]
                            for n in xrange(len(self.view.custombuttons)):
                                self.cbutton_save(n, self.view.custombuttons[n])
                            os.rename("custombtn.txt", "custombtn.old")
                            rco = open("custombtn.txt", "w")
                            rco.write(_("# I moved all your custom buttons into .pronsolerc.\n# Please don't add them here any more.\n# Backup of your old buttons is in custombtn.old\n"))
                            rco.close()
                        except IOError, x:
                            print str(x)
                    else:
                        print _("Note!!! You have specified custom buttons in both custombtn.txt and .pronsolerc")
                        print _("Ignoring custombtn.txt. Remove all current buttons to revert to custombtn.txt")

            except:
                pass    
        
    def homebuttonclicked(self, corner): 
        if corner == 0: # upper-left
            self.model.onecmd('home X')
        if corner == 1: # upper-right
            self.model.onecmd('home Y')
        if corner == 2: # lower-right
            self.model.onecmd('home Z')
        if corner == 3: # lower-left
            self.model.onecmd('home')
        # When user clicks on the XY control, the Z control no longer gets spacebar/repeat signals
        self.view.zb.clearRepeat()
    
    def spacebaraction(self, event):
        self.view.zb.repeatLast()
        self.view.xyb.repeatLast()   
    
    def moveZ(self, z):
        if z != 0:
            self.model.onecmd('move Z %s' % z)
        # When user clicks on the Z control, the XY control no longer gets spacebar/repeat signals
        self.view.xyb.clearRepeat()
    
    def doneediting(self, gcode):
        f = open(self.filename, "w")
        f.write("\n".join(gcode))
        f.close()
        wx.CallAfter(self.loadfile, None, self.model.filename)
 
    def connect(self, event):
        print _("Connecting...")
        port = None
        try:
            port = self.model.scanserial()[0]
        except:
            pass
        if self.view.serialport.GetValue()!="":
            port = str(self.view.serialport.GetValue())
        baud = 115200
        try:
            baud = int(self.view.baud.GetValue())
        except:
            pass
        if self.model.paused:
            self.model.p.paused = 0
            self.model.p.printing = 0
            self.view.setpausebuttonlabel(_("Pause"))
            self.view.setprintbuttonlabel(_("Pause"))
            self.model.paused = 0
            if self.model.sdprinting:
                self.model.p.send_now("M26 S0")
        self.model.p.connect(port, baud)
        self.model.statuscheck = True
        if port != self.model.settings.port:
            self.model.set("port", port)
        if baud != self.model.settings.baudrate:
            self.model.set("baudrate", str(baud))
        self.model.status_thread = threading.Thread(target = self.model.statuschecker)
        self.model.status_thread.start()
        if self.model.predisconnect_mainqueue:
            self.view.enablerecoverbutton
    
    def plate(self, e):
        import plater
        print "plate function activated"
        plater.stlwin(size = (800, 580), callback = self.platecb, parent = self).Show()
    
    def sdmenu(self, e):
        obj = e.GetEventObject()
        popupmenu = wx.Menu()
        item = popupmenu.Append(-1, _("SD Upload"))
        if not self.model.f or not len(self.model.f):
            item.Enable(False)
        self.view.Bind(wx.EVT_MENU, self.upload, id = item.GetId())
        item = popupmenu.Append(-1, _("SD Print"))
        self.view.Bind(wx.EVT_MENU, self.sdprintfile, id = item.GetId())
        self.panel.PopupMenu(popupmenu, obj.GetPosition())
    
    def upload(self, event):
        if not self.model.f or not len(self.model.f):
            return
        if not self.model.p.online:
            return
        dlg = wx.TextEntryDialog(self.view, ("Enter a target filename in 8.3 format:"), _("Pick SD filename") ,dosify(self.model.filename))
        if dlg.ShowModal() == wx.ID_OK:
            self.model.p.send_now("M21")
            self.model.p.send_now("M28 "+str(dlg.GetValue()))
            self.model.recvlisteners+=[self.model.uploadtrigger]
            
    def sdprintfile(self, event):
        self.model.on_startprint()
        threading.Thread(target = self.model.getfiles).start()
    
    def printfile(self, event):
        self.model.extra_print_time = 0
        if self.model.paused:
            self.model.p.paused = 0
            self.model.paused = 0
            self.model.on_startprint()
            if self.model.sdprinting:
                self.model.p.send_now("M26 S0")
                self.model.p.send_now("M24")
                return

        if self.model.f is None or not len(self.model.f):
            self.view.setstatustext(_("No file loaded. Please use load first."))
            return
        if not self.model.p.online:
            self.view.setstatustext( _("Not connected to printer."))
            return
        self.model.on_startprint()
        self.model.p.startprint(self.f)
     
    def pause(self, event):
        print _("Paused.")
        if not self.model.paused:
            if self.model.sdprinting:
                self.model.p.send_now("M25")
            else:
                if(not self.model.p.printing):
                    #print "Not printing, cannot pause."
                    return
                self.model.p.pause()
            self.model.paused = True
            self.model.extra_print_time += int(time.time() - self.model.starttime)
            self.view.setpausebuttonlabel(_("Resume"))
        else:
            self.model.paused = False
            if self.model.sdprinting:
                self.model.p.send_now("M24")
            else:
                self.model.p.resume()
                self.view.setpausebuttonlabel(_("Pause"))

    def recover(self, event):
        self.model.extra_print_time = 0
        if not self.modelp.online:
            self.view.setstatustext(_("Not connected to printer."))
            return
        # Reset Z
        self.model.p.send_now("G92 Z%f" % self.model.predisconnect_layer)
        # Home X and Y
        self.model.p.send_now("G28 X Y")
        self.model.on_startprint()
        self.model.p.startprint(self.model.predisconnect_mainqueue, self.model.p.queueindex)     
    
    def setmonitor(self, e):
        self.model.monitor = self.view.monitorbox.GetValue()
        if self.model.monitor:
            wx.CallAfter(self.view.graph.StartPlotting, 1000)
        else:
            wx.CallAfter(self.view.graph.StopPlotting)
     
    def do_settemp(self, l = ""):
        try:
            if not l.__class__ in (str, unicode) or not len(l):
                l = str(self.view.htemp.GetValue().split()[0])
            l = l.lower().replace(", ", ".")
            for i in self.model.temps.keys():
                l = l.replace(i, self.model.temps[i])
            f = float(l)
            if f >= 0:
                if self.model.p.online:
                    self.model.p.send_now("M104 S"+l)
                    print _("Setting hotend temperature to %f degrees Celsius.") % f
                    self.sethotendgui(f)
                else:
                    print _("Printer is not online.")
            else:
                print _("You cannot set negative temperatures. To turn the hotend off entirely, set its temperature to 0.")
        except Exception, x:
            print _("You must enter a temperature. (%s)") % (repr(x),)
            if self.model.webInterface:
                self.model.webInterface.AddLog("You must enter a temperature. (%s)" % (repr(x),))
     
    def sethotendgui(self, f):
        self.model.hsetpoint = f
        wx.CallAfter(self.view.graph.SetExtruder0TargetTemperature, int(f))
        if f > 0:
            wx.CallAfter(self.view.htemp.SetValue, str(f))
            self.model.set("last_temperature", str(f))
            wx.CallAfter(self.view.settoff.SetBackgroundColour, "")
            wx.CallAfter(self.view.settoff.SetForegroundColour, "")
            wx.CallAfter(self.view.settbtn.SetBackgroundColour, "#FFAA66")
            wx.CallAfter(self.view.settbtn.SetForegroundColour, "#660000")
            wx.CallAfter(self.view.htemp.SetBackgroundColour, "#FFDABB")
        else:
            wx.CallAfter(self.view.settoff.SetBackgroundColour, "#0044CC")
            wx.CallAfter(self.view.settoff.SetForegroundColour, "white")
            wx.CallAfter(self.view.settbtn.SetBackgroundColour, "")
            wx.CallAfter(self.view.settbtn.SetForegroundColour, "")
            wx.CallAfter(self.view.htemp.SetBackgroundColour, "white")
            wx.CallAfter(self.view.htemp.Refresh)
    
    def htemp_change(self, event):
        if self.model.hsetpoint > 0:
            self.do_settemp("")
        wx.CallAfter(self.view.htemp.SetInsertionPoint, 0)  
    
    def do_bedtemp(self, l = ""):
        try:
            if not l.__class__ in (str, unicode) or not len(l):
                l = str(self.view.btemp.GetValue().split()[0])
            l = l.lower().replace(", ", ".")
            for i in self.model.bedtemps.keys():
                l = l.replace(i, self.model.bedtemps[i])
            f = float(l)
            if f >= 0:
                if self.model.p.online:
                    self.model.p.send_now("M140 S"+l)
                    print _("Setting bed temperature to %f degrees Celsius.") % f
                    self.setbedgui(f)
                else:
                    print _("Printer is not online.")
                    if self.model.webInterface:
                        self.model.webInterface.AddLog("Printer is not online.")
            else:
                print _("You cannot set negative temperatures. To turn the bed off entirely, set its temperature to 0.")
                if self.model.webInterface:
                    self.model.webInterface.AddLog("You cannot set negative temperatures. To turn the bed off entirely, set its temperature to 0.")
        except Exception, x:
            print _("You must enter a temperature. (%s)") % (repr(x),)
            if self.model.webInterface:
                self.model.webInterface.AddLog("You must enter a temperature.")
 
    def setbedgui(self, f):
        self.model.bsetpoint = f
        wx.CallAfter(self.view.graph.SetBedTargetTemperature, int(f))
        if f>0:
            wx.CallAfter(self.view.btemp.SetValue, str(f))
            self.model.set("last_bed_temperature", str(f))
            wx.CallAfter(self.view.setboff.SetBackgroundColour, "")
            wx.CallAfter(self.view.setboff.SetForegroundColour, "")
            wx.CallAfter(self.view.setbbtn.SetBackgroundColour, "#FFAA66")
            wx.CallAfter(self.view.setbbtn.SetForegroundColour, "#660000")
            wx.CallAfter(self.view.btemp.SetBackgroundColour, "#FFDABB")
        else:
            wx.CallAfter(self.view.setboff.SetBackgroundColour, "#0044CC")
            wx.CallAfter(self.view.setboff.SetForegroundColour, "white")
            wx.CallAfter(self.view.setbbtn.SetBackgroundColour, "")
            wx.CallAfter(self.view.setbbtn.SetForegroundColour, "")
            wx.CallAfter(self.view.btemp.SetBackgroundColour, "white")
            wx.CallAfter(self.view.btemp.Refresh)
    
    def btemp_change(self, event):
        if self.model.bsetpoint > 0:
            self.do_bedtemp("")
        wx.CallAfter(self.view.btemp.SetInsertionPoint, 0)
     
    def setfeeds(self, e):
        self.model.feedrates_changed = True
        try:
            self.model.settings._set("e_feedrate", self.view.efeedc.GetValue())
        except:
            pass
        try:
            self.model.settings._set("z_feedrate", self.view.zfeedc.GetValue())
        except:
            pass
        try:
            self.model.settings._set("xy_feedrate", self.view.xyfeedc.GetValue())
        except:
            pass
    
    def reset(self, event):
        print _("Reset.")
        dlg = wx.MessageDialog(self.view, _("Are you sure you want to reset the printer?"), _("Reset?"), wx.YES|wx.NO)
        if dlg.ShowModal() == wx.ID_YES:
            self.model.p.reset()
            self.sethotendgui(0)
            self.setbedgui(0)
            self.model.p.printing = 0
            self.view.setprintbuttonlabel(_("Print"))
            if self.model.paused:
                self.model.p.paused = 0
                self.view.setpausebuttonlabel(_("Pause"))
                self.model.paused = 0
     
    def showwin(self, event):
        if(self.model.f is not None):
            self.view.gwindow.Show(True)
            self.view.gwindow.SetToolTip(wx.ToolTip("Mousewheel zooms the display\nShift / Mousewheel scrolls layers"))
            self.view.gwindow.Raise()
            
    def cbkey(self, e):
        if e.GetKeyCode() == wx.WXK_UP:
            if self.view.commandbox.histindex == len(self.view.commandbox.history):
                self.view.commandbox.history+=[self.view.commandbox.GetValue()] #save current command
            if len(self.view.commandbox.history):
                self.view.commandbox.histindex = (self.model.commandbox.histindex-1)%len(self.model.commandbox.history)
                self.model.commandbox.SetValue(self.model.commandbox.history[self.model.commandbox.histindex])
                self.model.commandbox.SetSelection(0, len(self.model.commandbox.history[self.model.commandbox.histindex]))
        elif e.GetKeyCode() == wx.WXK_DOWN:
            if self.model.commandbox.histindex == len(self.model.commandbox.history):
                self.model.commandbox.history+=[self.model.commandbox.GetValue()] #save current command
            if len(self.model.commandbox.history):
                self.model.commandbox.histindex = (self.model.commandbox.histindex+1)%len(self.model.commandbox.history)
                self.model.commandbox.SetValue(self.model.commandbox.history[self.model.commandbox.histindex])
                self.model.commandbox.SetSelection(0, len(self.model.commandbox.history[self.model.commandbox.histindex]))
        else:
            e.Skip()
    
    def loadviz(self):
        Xtot, Ytot, Ztot, Xmin, Xmax, Ymin, Ymax, Zmin, Zmax = pronsole.measurements(self.model.f)
        print pronsole.totalelength(self.model.f), _("mm of filament used in this print\n")
        print _("the print goes from %f mm to %f mm in X\nand is %f mm wide\n") % (Xmin, Xmax, Xtot)
        if self.model.webInterface:
            self.model.webInterface.AddLog(_("the print goes from %f mm to %f mm in X\nand is %f mm wide\n") % (Xmin, Xmax, Xtot))
        print _("the print goes from %f mm to %f mm in Y\nand is %f mm wide\n") % (Ymin, Ymax, Ytot)
        print _("the print goes from %f mm to %f mm in Z\nand is %f mm high\n") % (Zmin, Zmax, Ztot)
        try:
            print _("Estimated duration (pessimistic): "), pronsole.estimate_duration(self.f)
        except:
            pass
        #import time
        #t0 = time.time()
        self.view.gviz.clear()
        self.view.gwindow.p.clear()
        self.view.gviz.addfile(self.f)
        #print "generated 2d view in %f s"%(time.time()-t0)
        #t0 = time.time()
        self.view.gwindow.p.addfile(self.f)
        #print "generated 3d view in %f s"%(time.time()-t0)
        self.view.gviz.showall = 1
        wx.CallAfter(self.view.gviz.Refresh)
        
    #callback methods
    #----------------
    def clearoutput(self, evt):
        self.view.clearoutput
    def project(self, evt):
        self.model.project
    def do_skein(self, evt):
        self.model.do_skein(evt)
    def setloud(self, evt):
        self.model.setloud
    def rescanports(self, event):
        self.model.rescanports 
    def sendline(self, event):
        self.model.senline(event)
    
    #subscribe to model message throuhg wx.lib.pubsub
    #------------------------------------------------
    def subscribetomodel(self):
        pub.subscribe(self.serialportclear, "SERIALPORT_CLEAR")
        pub.subscribe(self.serialportappenditems, "SERIALPORT_APPENDITEMS")
        pub.subscribe(self.serialportsetvalue, "SERIALPORT_SETVALUE")
        pub.subscribe(self.logaddtext,"LOG_ADDTEXT")
        pub.subscribe(self.sentcbstrt,"SENTCB_START")
        pub.subscribe(self.sentcbsetextruder0targettemperature,"SENTCB_SETEXTRUDER0TARGETTEMPERATURE")
        pub.subscribe(self.sentcbsetbedtargettemperature,"SENTCB_SETBEDTARGETTEMPERATURE")
        pub.subscribe(self.guidisablepausebutton,"GUI_DISABLEPAUSEBUTTON")
        pub.subscribe(self.guisetprintbuttonlabel,"GUI_SETPRINTBUTTONLABEL")                     
        
    #subscribed model methods
    #------------------------
    def serialportclear(self, evt):
        self.view.serialportclear()
        
    def serialportappenditems(self, message):
        self.view.serialportappenditems(message.data)
        
    def serialportsetvalue(self, message):
        self.view.serialportsetvalue(message.data)
        
    def logaddtext(self, message):    
        wx.CallAfter(self.view.addtexttolog, message.data);
        
    def sentcbstrt(self, evt):
        threading.Thread(target = wx.CallAfter, args = (self.view.gviz.setlayer, layer)).start()
    
    def sentcbsetextruder0targettemperature(self, message):
        wx.CallAfter(self.view.graph.SetExtruder0TargetTemperature, message.data)
    
    def sentcbsetbedtargettemperature(self, message):
        wx.CallAfter(self.view.graph.SetBedTargetTemperature, message.data)
    
    def guidisablepausebutton(self, evt):
        enablepausebutton(False)
        
    def guisetprintbuttonlabel(selfself, message):
        self.view.setprintbuttonlabel(message.data)
  
        