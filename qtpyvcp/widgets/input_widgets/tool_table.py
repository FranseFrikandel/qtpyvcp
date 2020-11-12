from qtpy.QtCore import Qt, Slot, Property, QModelIndex, QSortFilterProxyModel
from qtpy.QtGui import QStandardItemModel, QColor, QBrush
from qtpy.QtWidgets import QTableView, QStyledItemDelegate, QDoubleSpinBox, \
    QSpinBox, QLineEdit, QMessageBox, QColorDialog, QFileDialog

from qtpyvcp.actions.machine_actions import issue_mdi

from qtpyvcp.utilities.settings import getSetting, connectSetting
from qtpyvcp.utilities.logger import getLogger
from qtpyvcp.plugins import getPlugin

LOG = getLogger(__name__)


class ItemDelegate(QStyledItemDelegate):

    def __init__(self, columns):
        super(ItemDelegate, self).__init__()

        self._columns = columns
        self._padding = ' ' * 2

    def setColumns(self, columns):
        self._columns = columns

    def displayText(self, value, locale):

        if type(value) == float:
            return "{0:.4f}".format(value)

        return "{}{}".format(self._padding, value)

    def createEditor(self, parent, option, index):
        # ToDo: set dec placed for IN and MM machines
        col = self._columns[index.column()]

        if col == 'R':
            editor = QLineEdit(parent)
            editor.setFrame(False)
            margins = editor.textMargins()
            padding = editor.fontMetrics().width(self._padding) + 1
            margins.setLeft(margins.left() + padding)
            editor.setTextMargins(margins)
            return editor

        elif col in ('T', 'P', 'Q'):
            editor = QSpinBox(parent)
            editor.setFrame(False)
            editor.setAlignment(Qt.AlignCenter)
            if col == 'Q':
                editor.setMaximum(9)
            else:
                editor.setMaximum(99999)
            return editor

        elif col in ('X', 'Y', 'Z', 'A', 'B', 'C', 'U', 'V', 'W', 'D'):
            editor = QDoubleSpinBox(parent)
            editor.setFrame(False)
            editor.setAlignment(Qt.AlignCenter)
            editor.setDecimals(4)
            # editor.setStepType(QSpinBox.AdaptiveDecimalStepType)
            editor.setProperty('stepType', 1)  # stepType was added in 5.12
            editor.setRange(-1000, 1000)
            return editor

        elif col in ('I', 'J'):
            editor = QDoubleSpinBox(parent)
            editor.setFrame(False)
            editor.setAlignment(Qt.AlignCenter)
            editor.setMaximum(360.0)
            editor.setMinimum(0.0)
            editor.setDecimals(4)
            # editor.setStepType(QSpinBox.AdaptiveDecimalStepType)
            editor.setProperty('stepType', 1)  # stepType was added in 5.12
            return editor

        elif col in ('HOLDER_STL', 'TOOL_STL'):
            editor = QFileDialog(parent)
            # editor.setFrame(False)
            # margins = editor.textMargins()
            # padding = editor.fontMetrics().width(self._padding) + 1
            # margins.setLeft(margins.left() + padding)
            # editor.setTextMargins(margins)
            return editor

        elif col == 'PATH_COLOR':
            editor = QColorDialog(parent)
            # editor.setFrame(False)
            # margins = editor.textMargins()
            # padding = editor.fontMetrics().width(self._padding) + 1
            # margins.setLeft(margins.left() + padding)
            # editor.setTextMargins(margins)
            return editor

        return None


class ToolModel(QStandardItemModel):
    def __init__(self, parent=None):
        super(ToolModel, self).__init__(parent)

        self.status = getPlugin('status')
        self.stat = self.status.stat
        self.tt = getPlugin('tooltable')

        self.current_tool_color = QColor(Qt.darkGreen)
        self.current_tool_bg = None

        self._columns = self.tt.columns
        self._column_labels = self.tt.COLUMN_LABELS

        self._tool_table = self.tt.getToolTable()

        self.setColumnCount(self.columnCount())
        self.setRowCount(1000)  # (self.rowCount())

        self.status.tool_in_spindle.notify(self.refreshModel)
        self.tt.tool_table_changed.connect(self.updateModel)

    def refreshModel(self):
        # refresh model so current tool gets highlighted
        self.beginResetModel()
        self.endResetModel()

    def updateModel(self, tool_table):
        # update model with new data
        self.beginResetModel()
        self._tool_table = tool_table
        self.endResetModel()

    def setColumns(self, columns):
        self._columns = columns
        self.setColumnCount(len(columns))

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:


            return self._column_labels[self._columns[section]]

        return QStandardItemModel.headerData(self, section, orientation, role)

    def columnCount(self, parent=None):
        return len(self._columns)

    def rowCount(self, parent=None):
        return len(self._tool_table) - 1

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole or role == Qt.EditRole:
            key = self._columns[index.column()]
            tnum = sorted(self._tool_table)[index.row() + 1]
            return self._tool_table[tnum][key]

        elif role == Qt.TextAlignmentRole:
            col = self._columns[index.column()]
            if col == 'R':      # Remark
                return Qt.AlignVCenter | Qt.AlignLeft
            elif col in ('T', 'P', 'Q'):  # Integers (Tool, Pocket, Orient)
                return Qt.AlignVCenter | Qt.AlignCenter
            else:               # All the other floats
                return Qt.AlignVCenter | Qt.AlignRight

        elif role == Qt.TextColorRole:
            tnum = sorted(self._tool_table)[index.row() + 1]
            if self.stat.tool_in_spindle == tnum:
                return QBrush(self.current_tool_color)
            else:
                return QStandardItemModel.data(self, index, role)

        elif role == Qt.BackgroundRole and self.current_tool_bg is not None:
            tnum = sorted(self._tool_table)[index.row() + 1]
            if self.stat.tool_in_spindle == tnum:
                return QBrush(self.current_tool_bg)
            else:
                return QStandardItemModel.data(self, index, role)

        return QStandardItemModel.data(self, index, role)

    def setData(self, index, value, role):
        key = self._columns[index.column()]
        tnum = sorted(self._tool_table)[index.row() + 1]
        self._tool_table[tnum][key] = value
        return True

    def removeTool(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        tnum = sorted(self._tool_table)[row + 1]
        del self._tool_table[tnum]
        self.endRemoveRows()
        return True

    def addTool(self):
        try:
            tnum = sorted(self._tool_table)[-1] + 1
        except IndexError:
            tnum = 1

        row = len(self._tool_table) - 1

        if row == 9999:
            # max 56 tools
            return False

        self.beginInsertRows(QModelIndex(), row, row)
        self._tool_table[tnum] = self.tt.newTool(tnum=tnum)
        self.endInsertRows()
        return True

    def toolDataFromRow(self, row):
        """Returns dictionary of tool data"""
        tnum = sorted(self._tool_table)[row + 1]
        return self._tool_table[tnum]

    def saveToolTable(self):
        self.tt.saveToolTable(self._tool_table, self._columns)
        return True

    def clearToolTable(self):
        self.beginRemoveRows(QModelIndex(), 0, 100)
        # delete all but the spindle, which can't be deleted
        self._tool_table = {0: self._tool_table[0]}
        self.endRemoveRows()
        return True

    def loadToolTable(self):
        # the tooltable plugin will emit the tool_table_changed signal
        # so we don't need to do any more here
        self.tt.loadToolTable()
        return True


class ToolTable(QTableView):
    def __init__(self, parent=None):
        super(ToolTable, self).__init__(parent)

        # Properties

        self._columns = list()
        self._confirm_actions = False
        self._current_tool_color = QColor('sage')
        self._current_tool_bg = None

        self.tool_model = ToolModel(self)
        self.item_delegate = ItemDelegate(columns=self._columns)
        self.setItemDelegate(self.item_delegate)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(0)
        self.proxy_model.setSourceModel(self.tool_model)

        self.setModel(self.proxy_model)

        # Appearance/Behaviour settings

        self.setSortingEnabled(True)
        self.verticalHeader().hide()
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)


        # Settings

        self.showX(getSetting('tool_table.column_x'))
        self.showY(getSetting('tool_table.column_y'))
        self.showZ(getSetting('tool_table.column_z'))

        self.showA(getSetting('tool_table.column_a'))
        self.showB(getSetting('tool_table.column_b'))
        self.showC(getSetting('tool_table.column_c'))

        self.showU(getSetting('tool_table.column_u'))
        self.showV(getSetting('tool_table.column_v'))
        self.showW(getSetting('tool_table.column_w'))

        self.showP(getSetting('tool_table.column_p'))
        self.showQ(getSetting('tool_table.column_q'))
        self.showT(getSetting('tool_table.column_t'))

        self.showR(getSetting('tool_table.column_r'))

        self.showHolderSTL(getSetting('tool_table.column_holder_stl'))
        self.showToolSTL(getSetting('tool_table.column_tool_stl'))
        self.showPathColor(getSetting('tool_table.column_path_color'))

        connectSetting('tool_table.column_x', self.showX)
        connectSetting('tool_table.column_y', self.showY)
        connectSetting('tool_table.column_z', self.showZ)

        connectSetting('tool_table.column_a', self.showA)
        connectSetting('tool_table.column_b', self.showB)
        connectSetting('tool_table.column_c', self.showC)

        connectSetting('tool_table.column_u', self.showU)
        connectSetting('tool_table.column_v', self.showV)
        connectSetting('tool_table.column_w', self.showW)

        connectSetting('tool_table.column_p', self.showP)
        connectSetting('tool_table.column_q', self.showQ)
        connectSetting('tool_table.column_t', self.showT)

        connectSetting('tool_table.column_r', self.showR)

        connectSetting('tool_table.column_holder_stl', self.showHolderSTL)
        connectSetting('tool_table.column_tool_stl', self.showToolSTL)
        connectSetting('tool_table.column_path_color', self.showPathColor)


    @Slot()
    def saveToolTable(self):
        if not self.confirmAction("Do you want to save changes and\n"
                                  "load tool table into LinuxCNC?"):
            return
        self.tool_model.saveToolTable()

    @Slot()
    def loadToolTable(self):
        if not self.confirmAction("Do you want to re-load the tool table?\n"
                                  "All unsaved changes will be lost."):
            return
        self.tool_model.loadToolTable()

    @Slot()
    def deleteSelectedTool(self):
        """Delete the currently selected item"""
        current_row = self.selectedRow()
        if current_row == -1:
            # no row selected
            return

        tdata = self.tool_model.toolDataFromRow(current_row)
        if not self.confirmAction('Are you sure you want to delete T{tdata[T]}?\n'
                                  '"{tdata[R]}"'.format(tdata=tdata)):
            return

        self.tool_model.removeTool(current_row)

    @Slot()
    def selectPrevious(self):
        """Select the previous item in the view."""
        self.selectRow(self.selectedRow() - 1)
        return True

    @Slot()
    def selectNext(self):
        """Select the next item in the view."""
        self.selectRow(self.selectedRow() + 1)
        return True

    @Slot()
    def clearToolTable(self, confirm=True):
        """Remove all items from the model"""
        if confirm:
            if not self.confirmAction("Do you want to delete the whole tool table?"):
                return

        self.tool_model.clearToolTable()

    @Slot()
    def addTool(self):
        """Appends a new item to the model"""
        self.tool_model.addTool()
        self.selectRow(self.tool_model.rowCount() - 1)

    @Slot()
    def loadSelectedTool(self):
        """Loads the currently selected tool"""
        # see: https://forum.linuxcnc.org/41-guis/36042?start=50#151820
        current_row = self.selectedRow()
        if current_row == -1:
            # no row selected
            return

        tnum = self.tool_model.toolDataFromRow(current_row)['T']
        issue_mdi("T%s M6" % tnum)

    def selectedRow(self):
        """Returns the row number of the currently selected row, or 0"""
        return self.selectionModel().currentIndex().row()

    def confirmAction(self, message):
        if not self._confirm_actions:
            return True

        box = QMessageBox.question(self,
                                   'Confirm Action',
                                   message,
                                   QMessageBox.Yes,
                                   QMessageBox.No)
        if box == QMessageBox.Yes:
            return True
        else:
            return False

    def showX(self, enable):
        column = 'X'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showY(self, enable):
        column = 'Y'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showZ(self, enable):
        column = 'Z'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showA(self, enable):
        column = 'A'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showB(self, enable):
        column = 'B'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showC(self, enable):
        column = 'C'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showU(self, enable):
        column = 'U'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showV(self, enable):
        column = 'V'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showW(self, enable):
        column = 'W'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showP(self, enable):
        column = 'P'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showQ(self, enable):
        column = 'Q'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showT(self, enable):
        column = 'T'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showR(self, enable):
        column = 'R'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showPathColor(self, enable):
        column = 'PATH_COLOR'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showHolderSTL(self, enable):
        column = 'HOLDER_STL'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def showToolSTL(self, enable):
        column = 'TOOL_STL'
        if enable:
            self._columns.append(column)
        else:
            self._columns.remove(column)
        self.updateColumns()

    def updateColumns(self):
        self.tool_model.setColumns(self._columns)
        self.itemDelegate().setColumns(self._columns)

    @Property(bool)
    def confirmActions(self):
        return self._confirm_actions

    @confirmActions.setter
    def confirmActions(self, confirm):
        self._confirm_actions = confirm

    @Property(QColor)
    def currentToolColor(self):
        return self.tool_model.current_tool_color

    @currentToolColor.setter
    def currentToolColor(self, color):
        self.tool_model.current_tool_color = color

    @Property(QColor)
    def currentToolBackground(self):
        return self.tool_model.current_tool_bg or QColor()

    @currentToolBackground.setter
    def currentToolBackground(self, color):
        self.tool_model.current_tool_bg = color

    def insertToolAbove(self):
        # it does not make sense to insert tools, since the numbering
        # of all the other tools would have to change.
        self.addTool()
        raise DeprecationWarning("insertToolAbove() will be removed in "
                                 "the future, use addTool() instead")

    def insertToolBelow(self):
        self.addTool()
        raise DeprecationWarning("insertToolBelow() will be removed in "
                                 "the future, use addTool() instead")
