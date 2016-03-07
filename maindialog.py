# -*- coding: utf-8 -*-

# qgis-ol3 Creates OpenLayers map from QGIS layers
# Copyright (C) 2014 Victor Olaya (volayaf@gmail.com)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys
from collections import defaultdict
import webbrowser

# This import is to enable SIP API V2
# noinspection PyUnresolvedReferences
import qgis  # pylint: disable=unused-import
# noinspection PyUnresolvedReferences
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtWebKit import *
from PyQt4 import QtGui
import traceback
import logging

from ui_maindialog import Ui_MainDialog
import utils
from configparams import paramsOL, baselayers, specificParams, specificOptions
from olwriter import writeOL
from leafletWriter import *

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

selectedLineedit = "None"
selectedCombo = "None"
selectedLayerCombo = "None"
projectInstance = QgsProject.instance()


class MainDialog(QDialog, Ui_MainDialog):
    """The main dialog of QGIS2Web plugin."""
    items = {}

    def __init__(self, iface):
        QDialog.__init__(self)
        self.setupUi(self)
        self.iface = iface
        self.resize(QSettings().value("qgis2web/size", QSize(994, 647)))
        self.move(QSettings().value("qgis2web/pos", QPoint(50, 50)))
        self.paramsTreeOL.setSelectionMode(QAbstractItemView.SingleSelection)
        self.populate_layers_and_groups(self)
        self.populateConfigParams(self)
        self.populateMinMax()
        self.populateBasemaps()
        self.selectMapFormat()
        self.toggleOptions()
        self.previewMap()
        self.paramsTreeOL.itemClicked.connect(self.changeSetting)
        self.paramsTreeOL.itemChanged.connect(self.saveSettings)
        self.ol3.clicked.connect(self.changeFormat)
        self.leaflet.clicked.connect(self.changeFormat)
        self.buttonPreview.clicked.connect(self.previewMap)
        self.buttonExport.clicked.connect(self.saveMap)
        self.helpField.setSource(QUrl.fromLocalFile(os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "README.md")))
        self.devConsole = QWebInspector(self.verticalLayoutWidget_2)
        self.devConsole.setFixedHeight(0)
        self.devConsole.setObjectName("devConsole")
        self.devConsole.setPage(self.preview.page())
        self.verticalLayout_2.insertWidget(1, self.devConsole)
        self.filter = devToggleFilter()
        self.installEventFilter(self.filter)


    def changeFormat(self):
        global projectInstance
        projectInstance.writeEntry("qgis2web", "mapFormat",
                                   self.mapFormat.checkedButton().text())
        self.previewMap()
        self.toggleOptions()

    def toggleOptions(self):
        for param, value in specificParams.iteritems():
            treeParam = self.paramsTreeOL.findItems(param,
                                                    (Qt.MatchExactly |
                                                     Qt.MatchRecursive))[0]
            if self.mapFormat.checkedButton().text() == "OpenLayers 3":
                if value == "OL3":
                    treeParam.setDisabled(False)
                else:
                    treeParam.setDisabled(True)
            else:
                if value == "OL3":
                    treeParam.setDisabled(True)
                else:
                    treeParam.setDisabled(False)
        for option, value in specificOptions.iteritems():
            treeOptions = self.layersTree.findItems(option,
                                                    (Qt.MatchExactly |
                                                     Qt.MatchRecursive))
            for treeOption in treeOptions:
                if self.mapFormat.checkedButton().text() == "OpenLayers 3":
                    if value == "OL3":
                        treeOption.setDisabled(False)
                    else:
                        treeOption.setDisabled(True)
                else:
                    if value == "OL3":
                        treeOption.setDisabled(True)
                    else:
                        treeOption.setDisabled(False)

    def previewMap(self):
        try:
            if self.mapFormat.checkedButton().text() == "OpenLayers 3":
                MainDialog.previewOL3(self)
            else:
                MainDialog.previewLeaflet(self)
        except Exception as e:
            errorHTML = "<html>"
            errorHTML += "<head></head>"
            errorHTML += "<style>body {font-family: sans-serif;}</style>"
            errorHTML += "<body><h1>Error</h1>"
            errorHTML += "<p>qgis2web produced an error:</p><code>"
            errorHTML += traceback.format_exc().replace("\n", "<br />")
            errorHTML += "</code></body></html>"
            self.preview.setHtml(errorHTML)
            print traceback.format_exc()

    def saveMap(self):
        if self.mapFormat.checkedButton().text() == "OpenLayers 3":
            MainDialog.saveOL(self)
        else:
            MainDialog.saveLeaf(self)

    def changeSetting(self, paramItem, col):
        if hasattr(paramItem, "name") and paramItem.name == "Export folder":
            folder = QFileDialog.getExistingDirectory(self,
                                                      "Choose export folder",
                                                      paramItem.text(col),
                                                      QFileDialog.ShowDirsOnly)
            if folder != "":
                paramItem.setText(1, folder)

    def saveSettings(self, paramItem, col):
        global projectInstance
        if isinstance(paramItem._value, bool):
            projectInstance.writeEntry("qgis2web", paramItem.name,
                                       paramItem.checkState(col))
        else:
            projectInstance.writeEntry("qgis2web", paramItem.name,
                                       paramItem.text(col))
        if paramItem.name == "Match project CRS":
            baseLayer = self.basemaps
            if paramItem.checkState(col):
                baseLayer.setDisabled(True)
            else:
                baseLayer.setDisabled(False)

    def saveComboSettings(self, value):
        global selectedCombo, projectInstance
        if selectedCombo != "None":
            projectInstance.writeEntry("qgis2web", selectedCombo, value)
    
    def saveLineeditSettings(self, value):
        #global projectInstance
        global selectedLineedit, projectInstance
        if selectedLineedit != "None":
            #value = int(self.lineedit.text().replace(' ', ''))
            #print str(selectedLineedit)
            projectInstance.writeEntry("qgis2web", selectedLineedit, value)

    def saveLayerComboSettings(self, value):
        global selectedLayerCombo
        if selectedLayerCombo != "None":
            selectedLayerCombo.setCustomProperty("qgis2web/Info popup content",
                                                 value)
    
    def saveLayerTimeFromComboSettings(self, value):
        global selectedLayerCombo
        if selectedLayerCombo != "None":
            selectedLayerCombo.setCustomProperty("qgis2web/Time from",
                                                 value)
            self.populateMinMax()
                                                             
    def saveLayerTimeToComboSettings(self, value):
        global selectedLayerCombo
        if selectedLayerCombo != "None":
            selectedLayerCombo.setCustomProperty("qgis2web/Time to",
                                                 value)
            self.populateMinMax()
                                         
    def populate_layers_and_groups(self, dlg):
        """Populate layers on QGIS into our layers and group tree view."""
        root_node = QgsProject.instance().layerTreeRoot()
        tree_groups = []
        tree_layers = root_node.findLayers()
        self.layers_item = QTreeWidgetItem()
        self.layers_item.setText(0, "Layers and Groups")

        for tree_layer in tree_layers:
            layer = tree_layer.layer()
            if layer.type() != QgsMapLayer.PluginLayer:
                try:
                    if layer.type() == QgsMapLayer.VectorLayer:
                        testDump = layer.rendererV2().dump()
                    layer_parent = tree_layer.parent()
                    if layer_parent.parent() is None:
                        item = TreeLayerItem(self.iface, layer,
                                             self.layersTree, dlg)
                        self.layers_item.addChild(item)
                    else:
                        if layer_parent not in tree_groups:
                            tree_groups.append(layer_parent)
                except:
                    pass

        for tree_group in tree_groups:
            group_name = tree_group.name()
            group_layers = [
                tree_layer.layer() for tree_layer in tree_group.findLayers()]
            item = TreeGroupItem(group_name, group_layers, self.layersTree)
            self.layers_item.addChild(item)

        self.layersTree.addTopLevelItem(self.layers_item)
        self.layersTree.expandAll()
        self.layersTree.resizeColumnToContents(0)
        self.layersTree.resizeColumnToContents(1)
        for i in xrange(self.layers_item.childCount()):
            item = self.layers_item.child(i)
            if item.checkState(0) != Qt.Checked:
                item.setExpanded(False)
    
    #ruzicka
    #TODO 
    def populateMinMax(self):
        global projectInstance
        min = 10000;
        max = 0;
        root_node = QgsProject.instance().layerTreeRoot()
        tree_layers = root_node.findLayers()
        for tree_layer in tree_layers:
            layer = tree_layer.layer()
            if layer.type() == QgsMapLayer.VectorLayer:
                for feat in layer.getFeatures():
                    attrs = feat.attributes()
                    attr = int(attrs[int(layer.customProperty("qgis2web/Time from")) - 1])
                    if attr < min:
                        min = attr
                    attr2 = int(attrs[int(layer.customProperty("qgis2web/Time to")) - 1])
                    if attr2 > max:
                        max = attr2
                    #attr = attrs[2]
                    #print str(attr)
                    #print str(layer.customProperty("qgis2web/Time from"))
        #print str(min)
        #print str(max)    
        projectInstance.writeEntry("qgis2web", "Min", min)
        projectInstance.writeEntry("qgis2web", "Max", max)
        self.items["Time axis"]["Min"].lineedit.setText(str(min))
        self.items["Time axis"]["Max"].lineedit.setText(str(max))

    def populateConfigParams(self, dlg):
        global selectedCombo, projectInstance
        self.items = defaultdict(dict)
        for group, settings in paramsOL.iteritems():
            item = QTreeWidgetItem()
            item.setText(0, group)
            for param, value in settings.iteritems():
                isTuple = False
                if isinstance(value, bool):
                    if projectInstance.readBoolEntry("qgis2web",
                                                     param)[0] == 2:
                        value = True
                    if projectInstance.readBoolEntry("qgis2web",
                                                     param)[0] == 0:
                        value = False
                elif isinstance(value, int):
                    if projectInstance.readNumEntry("qgis2web",
                                                    param)[0] != 0:
                        value = projectInstance.readNumEntry("qgis2web",
                                                             param)[0]
                elif isinstance(value, tuple):
                    selectedCombo = param
                    isTuple = True
                    if projectInstance.readNumEntry("qgis2web",
                                                    param)[0] != 0:
                        comboSelection = projectInstance.readNumEntry(
                            "qgis2web", param)[0]
                    elif param == "Max zoom level":
                        comboSelection = 27
                    elif param == "Precision":
                        comboSelection = 5
                    else:
                        comboSelection = 0
                else:
                    if (isinstance(projectInstance.readEntry("qgis2web",
                                   param)[0], basestring) and
                            projectInstance.readEntry("qgis2web",
                                                      param)[0] != ""):
                        value = projectInstance.readEntry("qgis2web", param)[0]
                subitem = TreeSettingItem(item, self.paramsTreeOL,
                                          param, value, dlg)
                if isTuple:
                    dlg.paramsTreeOL.itemWidget(subitem,
                                                1).setCurrentIndex(
                                                    comboSelection)
                item.addChild(subitem)
                self.items[group][param] = subitem
                #print """GROUP: """ + str(group)
                #print """PARAM: """ + str(param)
            self.paramsTreeOL.addTopLevelItem(item)
            item.sortChildren(0, Qt.AscendingOrder)
        self.paramsTreeOL.expandAll()
        self.paramsTreeOL.resizeColumnToContents(0)
        self.paramsTreeOL.resizeColumnToContents(1)

    def populateBasemaps(self):
        multiSelect = QtGui.QAbstractItemView.ExtendedSelection
        self.basemaps.setSelectionMode(multiSelect)
        attrFields = []
        for i in range(len(baselayers)):
            for key in baselayers[i]:
                attrFields.append(key)
        self.basemaps.addItems(attrFields)

    def selectMapFormat(self):
        global projectInstance
        if projectInstance.readEntry("qgis2web", "mapFormat")[0] == "Leaflet":
            self.ol3.setChecked(False)
            self.leaflet.setChecked(True)

    def tempIndexFile(self):
        folder = utils.tempFolder()
        url = "file:///" + os.path.join(folder,
                                        "index.html").replace("\\", "/")
        return url

    def previewOL3(self):
        self.preview.settings().clearMemoryCaches()
        (layers, groups, popup, visible,
         json, cluster) = self.getLayersAndGroups()
        params = self.getParameters()
        previewFile = writeOL(self.iface, layers, groups, popup, visible, json,
                              cluster, params, utils.tempFolder())
        self.preview.setUrl(QUrl.fromLocalFile(previewFile))

    def previewLeaflet(self):
        self.preview.settings().clearMemoryCaches()
        (layers, groups, popup, timefrom, timeto, visible,
         json, cluster) = self.getLayersAndGroups()
        params = self.getParameters()
        previewFile = writeLeaflet(self.iface, utils.tempFolder(), layers,
                                   visible, cluster, json, params, popup, timefrom, timeto)
        self.preview.setUrl(QUrl.fromLocalFile(previewFile))

    def saveOL(self):
        params = self.getParameters()
        folder = params["Data export"]["Export folder"]
        if folder:
            (layers, groups, popup, visible,
             json, cluster) = self.getLayersAndGroups()
            outputFile = writeOL(self.iface, layers, groups, popup, visible,
                                 json, cluster, params, folder)
            webbrowser.open_new_tab(outputFile)

    def saveLeaf(self):
        params = self.getParameters()
        folder = params["Data export"]["Export folder"]
        if folder:
            (layers, groups, popup, timefrom, timeto, visible,
             json, cluster) = self.getLayersAndGroups()
            outputFile = writeLeaflet(self.iface, folder, layers, visible,
                                      cluster, json, params, popup, timefrom, timeto)
            webbrowser.open_new_tab(outputFile)

    def getParameters(self):
        parameters = defaultdict(dict)
        for group, settings in self.items.iteritems():
            for param, item in settings.iteritems():
                parameters[group][param] = item.value()
        basemaps = self.basemaps.selectedItems()
        parameters["Appearance"]["Base layer"] = basemaps
        return parameters

    def getLayersAndGroups(self):
        layers = []
        groups = {}
        popup = []
        timefrom = []
        timeto = []
        visible = []
        json = []
        cluster = []
        for i in xrange(self.layers_item.childCount()):
            item = self.layers_item.child(i)
            if isinstance(item, TreeLayerItem):
                if item.checkState(0) == Qt.Checked:
                    layers.append(item.layer)
                    popup.append(item.popup)
                    timefrom.append(item.timefrom)
                    timeto.append(item.timeto)
                    visible.append(item.visible)
                    json.append(item.json)
                    cluster.append(item.cluster)
            else:
                group = item.name
                groupLayers = []
                if item.checkState(0) != Qt.Checked:
                    continue
                for layer in item.layers:
                    groupLayers.append(layer)
                    layers.append(layer)
                    popup.append(utils.NO_POPUP)
                    timefrom.append(utils.NO_TIME)
                    timeto.append(utils.NO_TIME)
                    if item.visible:
                        visible.append(True)
                    else:
                        visible.append(False)
                    if hasattr(item, "json") and item.json:
                        json.append(True)
                    else:
                        json.append(False)
                    if hasattr(item, "cluster") and item.cluster:
                        cluster.append(True)
                    else:
                        cluster.append(False)
                groups[group] = groupLayers[::-1]

        return (layers[::-1],
                groups,
                popup[::-1],
                timefrom[::-1],
                timeto[::-1],
                visible[::-1],
                json[::-1],
                cluster[::-1])

    def closeEvent(self, event):
        QSettings().setValue("qgis2web/size", self.size())
        QSettings().setValue("qgis2web/pos", self.pos())
        event.accept()


class devToggleFilter(QObject):
    devToggle = pyqtSignal()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_F12:
                self.devToggle.emit()
                if obj.devConsole.height() != 0:
                    obj.devConsole.setFixedHeight(0)
                else:
                    obj.devConsole.setFixedHeight(168)
                return True
        return False


class TreeGroupItem(QTreeWidgetItem):

    groupIcon = QIcon(os.path.join(os.path.dirname(__file__), "icons",
                                   "group.gif"))

    def __init__(self, name, layers, tree):
        QTreeWidgetItem.__init__(self)
        self.layers = layers
        self.name = name
        self.setText(0, name)
        self.setIcon(0, self.groupIcon)
        self.setCheckState(0, Qt.Checked)
        self.visibleItem = QTreeWidgetItem(self)
        self.visibleCheck = QCheckBox()
        self.visibleCheck.setChecked(True)
        self.visibleItem.setText(0, "Layers visibility")
        self.addChild(self.visibleItem)
        tree.setItemWidget(self.visibleItem, 1, self.visibleCheck)

    @property
    def visible(self):
        return self.visibleCheck.isChecked()


class TreeLayerItem(QTreeWidgetItem):

    layerIcon = QIcon(os.path.join(os.path.dirname(__file__), "icons",
                                   "layer.png"))

    def __init__(self, iface, layer, tree, dlg):
        global projectInstance
        QTreeWidgetItem.__init__(self)
        self.iface = iface
        self.layer = layer
        self.setText(0, layer.name())
        self.setIcon(0, self.layerIcon)
        if projectInstance.layerTreeRoot().findLayer(layer.id()).isVisible():
            self.setCheckState(0, Qt.Checked)
        else:
            self.setCheckState(0, Qt.Unchecked)
        if layer.type() == layer.VectorLayer:
            self.popupItem = QTreeWidgetItem(self)
            self.popupItem.setText(0, "Info popup content")
            self.combo = QComboBox()
            options = ["No popup", "Show all attributes"]
            for f in self.layer.pendingFields():
                options.append("FIELD:" + f.name())
            for option in options:
                self.combo.addItem(option)
            self.addChild(self.popupItem)
            if layer.customProperty("qgis2web/Info popup content"):
                self.combo.setCurrentIndex(int(
                    layer.customProperty("qgis2web/Info popup content")))
            self.combo.highlighted.connect(self.clickCombo)
            self.combo.currentIndexChanged.connect(dlg.saveLayerComboSettings)
            tree.setItemWidget(self.popupItem, 1, self.combo)
            
            #TODO
            #Remove no int or string fields or later handle other types
            self.timeFromItem = QTreeWidgetItem(self)
            self.timeFromItem.setText(0, "Time from")
            self.timeFromCombo = QComboBox()
            timeFromOptions = ["No time"]
            for f in self.layer.pendingFields():
                timeFromOptions.append("FIELD:" + f.name())
            for option in timeFromOptions:
                self.timeFromCombo.addItem(option)
            self.addChild(self.timeFromItem)
            if layer.customProperty("qgis2web/Time from"):
                self.timeFromCombo.setCurrentIndex(int(
                    layer.customProperty("qgis2web/Time from")))
            self.timeFromCombo.highlighted.connect(self.clickCombo)
            self.timeFromCombo.currentIndexChanged.connect(dlg.saveLayerTimeFromComboSettings)
            tree.setItemWidget(self.timeFromItem, 1, self.timeFromCombo)
            
            self.timeToItem = QTreeWidgetItem(self)
            self.timeToItem.setText(0, "Time to")
            self.timeToCombo = QComboBox()
            timeToOptions = ["No time"]
            for f in self.layer.pendingFields():
                timeToOptions.append("FIELD:" + f.name())
            for option in timeToOptions:
                self.timeToCombo.addItem(option)
            self.addChild(self.timeToItem)
            if layer.customProperty("qgis2web/Time to"):
                self.timeToCombo.setCurrentIndex(int(
                    layer.customProperty("qgis2web/Time to")))
            self.timeToCombo.highlighted.connect(self.clickCombo)
            self.timeToCombo.currentIndexChanged.connect(dlg.saveLayerTimeToComboSettings)
            tree.setItemWidget(self.timeToItem, 1, self.timeToCombo)
            
        self.visibleItem = QTreeWidgetItem(self)
        self.visibleCheck = QCheckBox()
        if layer.customProperty("qgis2web/Visible") == 0:
            self.visibleCheck.setChecked(False)
        else:
            self.visibleCheck.setChecked(True)
        self.visibleItem.setText(0, "Visible")
        self.visibleCheck.stateChanged.connect(self.changeVisible)
        self.addChild(self.visibleItem)
        tree.setItemWidget(self.visibleItem, 1, self.visibleCheck)
        if layer.type() == layer.VectorLayer:
            if layer.providerType() == 'WFS':
                self.jsonItem = QTreeWidgetItem(self)
                self.jsonCheck = QCheckBox()
                if layer.customProperty("qgis2web/Encode to JSON") == 2:
                    self.jsonCheck.setChecked(True)
                self.jsonItem.setText(0, "Encode to JSON")
                self.jsonCheck.stateChanged.connect(self.changeJSON)
                self.addChild(self.jsonItem)
                tree.setItemWidget(self.jsonItem, 1, self.jsonCheck)
            if layer.geometryType() == QGis.Point:
                self.clusterItem = QTreeWidgetItem(self)
                self.clusterCheck = QCheckBox()
                if layer.customProperty("qgis2web/Cluster") == 2:
                    self.clusterCheck.setChecked(True)
                self.clusterItem.setText(0, "Cluster")
                self.clusterCheck.stateChanged.connect(self.changeCluster)
                self.addChild(self.clusterItem)
                tree.setItemWidget(self.clusterItem, 1, self.clusterCheck)

    @property
    def popup(self):
        try:
            idx = self.combo.currentIndex()
            if idx < 2:
                popup = idx
            else:
                popup = self.combo.currentText()[len("FIELD:"):]
        except:
            popup = utils.NO_POPUP
        #print str(popup)
        return popup
    
    @property
    def timefrom(self):
        try:
            idx = self.timeFromCombo.currentIndex()
            #print """IDX: """ + str(idx)
            if idx < 1:
                timefrom = idx
            else:
                timefrom = self.timeFromCombo.currentText()[len("FIELD:"):]
        except:
            #print "Unexpected error:", sys.exc_info()[1]
            timefrom = utils.NO_TIME
        #print str(timefrom)
        return timefrom
    
    @property
    def timeto(self):
        try:
            idx = self.timeToCombo.currentIndex()
            #print """IDX: """ + str(idx)
            if idx < 1:
                timeto = idx
            else:
                timeto = self.timeToCombo.currentText()[len("FIELD:"):]
        except:
            #print "Unexpected error:", sys.exc_info()[1]
            timeto = utils.NO_TIME
        #print str(timefrom)
        return timeto

    @property
    def visible(self):
        return self.visibleCheck.isChecked()

    @property
    def json(self):
        try:
            return self.jsonCheck.isChecked()
        except:
            return False

    @property
    def cluster(self):
        try:
            return self.clusterCheck.isChecked()
        except:
            return False

    def clickCombo(self):
        global selectedLayerCombo
        selectedLayerCombo = self.layer

    def changeVisible(self, isVisible):
        self.layer.setCustomProperty("qgis2web/Visible", isVisible)

    def changeJSON(self, isJSON):
        self.layer.setCustomProperty("qgis2web/Encode to JSON", isJSON)

    def changeCluster(self, isCluster):
        self.layer.setCustomProperty("qgis2web/Cluster", isCluster)

    def changeLabel(self, isLabel):
        self.layer.setCustomProperty("qgis2web/Label", isLabel)

#TODO
#Set width of self.lineedit
class TreeSettingItem(QTreeWidgetItem):

    def __init__(self, parent, tree, name, value, dlg):
        QTreeWidgetItem.__init__(self, parent)
        self.parent = parent
        self.tree = tree
        self.name = name
        self._value = value
        self.setText(0, name)
        if isinstance(value, bool):
            if value:
                self.setCheckState(1, Qt.Checked)
            else:
                self.setCheckState(1, Qt.Unchecked)
        elif isinstance(value, tuple):
            self.combo = QComboBox()
            self.combo.setSizeAdjustPolicy(0)
            for option in value:
                self.combo.addItem(option)
            self.tree.setItemWidget(self, 1, self.combo)
            index = self.combo.currentIndex()
            self.combo.highlighted.connect(self.clickCombo)
            self.combo.currentIndexChanged.connect(dlg.saveComboSettings)
        elif isinstance(value, int):
            self.lineedit = QLineEdit()
            self.lineedit.setFixedWidth(10)
            self.lineedit.setMaximumWidth(20)
            self.lineedit.setText(str(value))
            self.tree.setItemWidget(self, 1, self.lineedit)
            text = int(self.lineedit.text().replace(' ', ''))
            self.lineedit.editingFinished.connect(self.clickLineedit)
            self.lineedit.textChanged.connect(dlg.saveLineeditSettings)
        else:
            self.setText(1, unicode(value))

    def clickCombo(self):
        global selectedCombo
        selectedCombo = self.name

    def clickLineedit(self):
        global selectedLineedit
        selectedLineedit = self.name

    def value(self):
        if isinstance(self._value, bool):
            return self.checkState(1) == Qt.Checked
        #elif isinstance(self._value, (int, float)):
            #return float(self.text(1))
        elif isinstance(self._value, int):
            return int(self.lineedit.text().replace(' ', ''))
        elif isinstance(self._value, tuple):
            return self.combo.currentText()
        else:
            return self.text(1)
