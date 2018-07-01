#!/usr/bin/env python

#   Copyright (c) 2017 Kurt Jacobson
#      <kurtcjacobson@gmail.com>
#
#   This file is part of PyQtUI.
#
#   PyQtUI is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 2 of the License, or
#   (at your option) any later version.
#
#   PyQtUI is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with PyQtUI.  If not, see <http://www.gnu.org/licenses/>.

# Description:
#   This module is used to get information from the machine's self.ini file.
#   It does some sanity checking to ensure it returns valid values.
#   If an self.ini entry does not exist, it may return a default value.

import os
import sys

from linuxcnc import ini

# Setup logging
from QtPyVCP.utilities import logger
log = logger.getLogger(__name__)


class Info(object):
    """Ensures only one instance of StatusPoller exists per python interpretor.
    """
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = _Info()
        return cls._instance


class _Info(object):

    INI_FILE = os.environ.get("INI_FILE_NAME")
    CONFIG_DIR =  os.environ.get('CONFIG_DIR')

    AXIS_LETTERS = 'xyzabcuvw'

    COORDINATES = 'xyz'
    NUM_AXES = 3
    NUM_JOINTS = 3

    # All example data is from the sim XYZY gantry config
    AXIS_LETTER_LIST = []   # Axes letters ['x', 'y', 'z'], no duplicates
    AXIS_NUMBER_LIST = []   # Axes numbers [0, 1, 2], no duplicates
    JOINT_AXIS_DICT = {}    # Joint:Axis correspondence {0: 0, 1: 1, 2: 2, 3: 1}
    DOUBLE_ALETTER = ""     # The letter of the double axis 'y'
    ALETTER_JNUM_DICT = {}  # Axis Letter:Joint correspondence {'x': 0, 'y0': 1, 'z': 2, 'y1': 3}
    JNUM_ALETTER_DICT = {}  # Joint:Axis Letter correspondence {0: 'x', 1: 'y0', 2: 'z', 3: 'y1'}

    def __init__(self, ini_file=None):
        super(_Info, self).__init__()

        if self.INI_FILE is None:
            self.INI_FILE = ini_file or '/dev/null'
            os.environ['INI_FILE_NAME'] = self.INI_FILE

        if self.CONFIG_DIR is None:
            self.CONFIG_DIR = os.path.dirname(self.INI_FILE)
            os.environ['CONFIG_DIR'] = self.CONFIG_DIR

        self.ini = ini(self.INI_FILE)

        self.getJointAxisMapping()

    def getMachineName(self):
        return self.ini.find('EMC', 'MACHINE') or "PyQtVCP Machine"

    def getFilePath(self, section, option, default):
        temp = self.ini.find(section, option) or default
        if temp is None:
            return
        elif temp.startswith('~'):
            path = os.path.expanduser(temp)
        elif not os.path.isabs(temp):
            path = os.path.join(self.CONFIG_DIR, temp)
        return os.path.realpath(path)

    def getUiFile(self, default='pyqtvcp.ui'):
        return self.getFilePath('DISPLAY', 'UI_FILE', default)

    def getPyFile(self, default='pyqtvcp.py'):
        return self.getFilePath('DISPLAY', 'PY_FILE', default)

    def getPyFile(self, default='pyqtvcp.css'):
        return self.getFilePath('DISPLAY', 'PY_FILE', default)

    def getLogFile(self, default='~/pyqtvcp.log'):
        return self.getFilePath('DISPLAY', 'LOG_FILE', default)

    def getPreferenceFile(self, default='~/pyqtvcp.pref'):
        return self.getFilePath('DISPLAY', 'PREFERENCE_FILE', default)

    def getMdiHystoryFile(self, default='~/.axis_mdi_history'):
        return self.getFilePath('DISPLAY', 'MDI_HISTORY_FILE', default)

    def getToolTableFile(self, default='tool.tbl'):
        return self.getFilePath('EMCIO', 'TOOL_TABLE', default)

    def getCoordinates(self):
        '''Returns [TRAJ] COORDINATES or xyz'''
        temp = self.ini.find('TRAJ', 'COORDINATES') or 'XYZ'
        temp = temp.replace(' ','')
        if not temp:
            log.warning("No [TRAJ] COORDINATES entry in self.ini, using XYZ")
            temp = "xyz"
        return temp.lower()

    def getNumberJoints(self):
        '''Returns value of [KINS] JOINTS or 3'''
        temp = self.ini.find('KINS', 'JOINTS')
        if not temp:
            log.warning("No [KINS] JOINTS entry in self.ini file, using 3")
            return (3)
        return int(temp)

    def getAxisList(self):
        return self.AXIS_LETTER_LIST

    def getIsMachineMetric(self):
        temp = self.ini.find('TRAJ', 'LINEAR_UNITS')
        if not temp:
            # Then get the X axis units
            temp = self.ini.find('AXIS_X', 'UNITS') or False
        if temp in ['mm', 'metric']:
            return True
        else:
            return False

    def getNoForceHoming(self):
        temp = self.ini.find('TRAJ', 'NO_FORCE_HOMING')
        if temp and temp == '1':
            return True
        return False

    def getPositionFeedback(self):
        temp = self.ini.find('DISPLAY', 'POSITION_FEEDBACK')
        if not temp or temp == "0":
            return True
        if temp.lower() == "actual":
            return True
        else:
            return False

    def getIsLathe(self):
        temp = self.ini.find('DISPLAY', 'LATHE')
        if not temp or temp == "0":
            return False
        return True

    def getIsBacktoolLathe(self):
        temp = self.ini.find('DISPLAY', 'BACK_TOOL_LATHE')
        if not temp or temp == "0":
            return False
        return True

    def getJogVelocity(self):
        # get default jog velocity
        # must convert from self.ini's units per second to hazzys's units per minute
        temp = self.ini.find('DISPLAY', 'DEFAULT_LINEAR_VELOCITY')
        if not temp:
            temp = 3.0
        return float(temp) * 60

    def getMaxJogVelocity(self):
        # get max jog velocity
        # must convert from self.ini's units per second to hazzy's units per minute
        temp = self.ini.find('DISPLAY', 'MAX_LINEAR_VELOCITY')
        if not temp:
            temp = 10.0
        return float(temp) * 60

    # ToDo : This may not be needed, as it could be recieved from linuxcnc.stat
    def getMaxVelocity(self):
        # max velocity settings: more then one place to check
        # This is the maximum velocity of the machine
        temp = self.ini.find('TRAJ', 'MAX_VELOCITY')
        if  temp == None:
            log.warning("No MAX_VELOCITY found in [TRAJ] of self.ini file. Using 15ipm")
            temp = 15.0
        return float(temp) * 60

    def getDefaultSpindleSpeed(self):
        # check for default spindle speed settings
        temp = self.ini.find('DISPLAY', 'DEFAULT_SPINDLE_SPEED')
        if not temp:
            temp = 300
            log.warning("No DEFAULT_SPINDLE_SPEED entry found in [DISPLAY] of self.ini file. Using 300rpm")
        return float(temp)

    def getMaxSpindleOverride(self):
        # check for override settings
        temp = self.ini.find('DISPLAY', 'MAX_SPINDLE_OVERRIDE')
        if not temp:
            temp = 1.0
            log.warning("No MAX_SPINDLE_OVERRIDE entry found in [DISPLAY] of self.ini file. Using 1.0")
        return float(temp)

    def getMinSpindleOverride(self):
        temp = self.ini.find('DISPLAY', 'MIN_SPINDLE_OVERRIDE')
        if not temp:
            temp = 0.1
            log.warning("No MIN_SPINDLE_OVERRIDE entry found in [DISPLAY] of self.ini file. Using 0.1")
        return float(temp)

    def getMaxFeedOverride(self):
        temp = self.ini.find('DISPLAY', 'MAX_FEED_OVERRIDE')
        if not temp:
            temp = 1.0
            log.warning("No MAX_FEED_OVERRIDE entry found in [DISPLAY] of self.ini file. Using 1.0")
        return float(temp)

    def getParameterFile(self):
        temp = self.ini.find('RS274NGC', 'PARAMETER_FILE')
        if not temp:
            return False
        return temp

    def getProgramPrefix(self):
        path = self.ini.find('DISPLAY', 'PROGRAM_PREFIX')
        if path:
            path = os.path.expanduser(path)
            if os.path.exists(path):
                return path
            else:
                log.warning("Path '{}' given in [DISPLAY] PROGRAM_PREFIX does not exist, "
                "trying '~/linuxcnc/nc_files'".format(path))

        path = os.path.expanduser("~/linuxcnc/nc_files")
        if os.path.exists(path):
            return path
        else:
            log.warning("Default path '~/linuxcnc/nc_files' does not exist, using '~/' as path")
            path = os.path.expanduser('~/')
            return path

    def getProgramExtentions(self):
        extensions = self.ini.findall("FILTER", "PROGRAM_EXTENSION")
        ext_list = ([ext.split(None, 1) for ext in extensions]) or None
        return ext_list

    def getGlobFilefilter(self):
        """Returns list of glob style file filters"""
        file_ext = self.ini.findall('FILTER', 'PROGRAM_EXTENSION')
        ext_list = ["*.ngc"]
        if file_ext:
            for data in file_ext:
                raw_ext = data.split(",")
                for extension in raw_ext:
                    ext = extension.split()
                    ext_list.append(ext[0].replace(".", "*."))
        else:
            log.error("Error converting file extensions in [FILTER] PROGRAM_EXTENSION, using default '*.ngc'")
        return ext_list

    def getQtFilefilter(self):
        """Returns Qt file filter string for use with QtFileDialoge"""
        qt_filter_list = [("G-code (*.ngc)")]
        extensions = self.getProgramExtentions()
        if extensions is not None:
            try:
                for extention, description in extensions:
                    extention = extention.replace(' ', '').replace(',', ' ').replace('.','*.')
                    description = description.strip()
                    qt_filter_list.append(( ';;{} ({})'.format(description, extention)))
                return ''.join(qt_filter_list)
            except:
                log.error("Error converting file extensions in [FILTER] PROGRAM_EXTENSION, using default '*.ngc'")
        return qt_filter_list[0]

    def getFilterProgram(self, fname):
        """Returns the filter program specified for processing this type of file"""
        ext = os.path.splitext(fname)[1]
        if ext:
            return self.ini.find("FILTER", ext[1:])
        else:
            return None

    def getIncrements(self):
        jog_increments = []
        increments = self.ini.find('DISPLAY', 'INCREMENTS')
        if increments:
            if "," in increments:
                for i in increments.split(","):
                    jog_increments.append(i.strip())
            else:
                jog_increments = increments.split()
            jog_increments.insert(0, 0)
        else:
            jog_increments = [ "0", "1.000", "0.100", "0.010", "0.001" ]
            log.warning("No default jog increments entry found in [DISPLAY] of self.ini file")
        return jog_increments

    def getSubroutinePaths(self):
        subroutines_paths = self.ini.find('RS274NGC', 'SUBROUTINE_PATH')
        if not subroutines_paths:
            log.info("No subroutine folder or program prefix given in self.ini file")
            subroutines_paths = program_prefix()
        if not subroutines_paths:
            return False
        return subroutines_paths

    def getRS274StartCode(self):
        temp = self.ini.find('RS274NGC', 'RS274NGC_STARTUP_CODE')
        if not temp:
            return False
        return  temp

    def getStartupNotification(self):
        return self.ini.find('DISPLAY', 'STARTUP_NOTIFICATION')

    def getStartupWarning(self):
        return self.ini.find('DISPLAY', 'STARTUP_WARNING')


    def getJointAxisMapping(self):

        self.COORDINATES = self.getCoordinates()
        self.NUM_JOINTS = self.getNumberJoints()

        # Joint:Axis dict (Ex. {0:0, 1:1, 2:2, 3:4})
        for jnum, aletter in enumerate(self.COORDINATES):
            # Axis letter list (Ex. ['X', 'Y', 'Z', 'B'])
            if aletter in self.AXIS_LETTER_LIST:
                continue
            self.AXIS_LETTER_LIST.append(aletter)

            # Axis number list (Ex. [0, 1, 2, 4])
            anum = self.AXIS_LETTERS.index(aletter)
            self.AXIS_NUMBER_LIST.append(anum)

            # Joint:Axis dict (Ex. {0:0, 1:1, 2:2, 3:4})
            self.JOINT_AXIS_DICT[jnum] = anum

        for aletter in self.AXIS_LETTERS:
            if self.COORDINATES.count(aletter) > 1:
                self.DOUBLE_ALETTER += aletter
        if self.DOUBLE_ALETTER != "":
            log.info("Machine appearers to be a gantry config having a double {0} axis"
                  .format(DOUBLE_ALETTER.upper()))

        self.NUM_AXES = len(self.AXIS_LETTER_LIST)
        if self.NUM_JOINTS == len(self.COORDINATES):
            log.info("The machine has {0} axes and {1} joints".format(self.NUM_AXES, self.NUM_JOINTS))
            log.info("The Axis/Joint mapping is:")
            count = 0
            for jnum, aletter in enumerate(self.COORDINATES):
                if aletter in self.DOUBLE_ALETTER:
                    aletter = aletter + str(count)
                    count += 1
                self.ALETTER_JNUM_DICT[aletter] = jnum
                self.JNUM_ALETTER_DICT[jnum] = aletter
                log.info("Axis {0} --> Joint {1}".format(aletter.upper(), jnum))
        else:
            log.info("The number of joints ({0}) is not equal to the number of coordinates ({1})"
                  .format(self.NUM_JOINTS, len(self.COORDINATES)))
            log.info("It is highly recommended that you update your config.")
            log.info("Reverting to old style. This could result in incorrect behavior...")
            log.info("\nGuessing Axes/Joints mapping:")
            for jnum, aletter in enumerate(AXIS_LETTERS):
                if aletter in self.COORDINATES:
                    self.ALETTER_JNUM_DICT[aletter] = jnum
                    log.info("Axis {0} --> Joint {1}".format(aletter, jnum))

        # print "AXIS_LETTER_LIST ", AXIS_LETTER_LIST
        # print "JOINT_AXIS_DICT, ", JOINT_AXIS_DICT
        # print "ALETTER_JNUM_DICT ", ALETTER_JNUM_DICT
        # print "JNUM_ALETTER_DICT ", JNUM_ALETTER_DICT