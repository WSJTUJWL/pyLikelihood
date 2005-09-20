"""
Python interface for binned likelihood.

@author J. Chiang <jchiang@slac.stanford.edu>
"""
#
# $Header: /nfs/slac/g/glast/ground/cvs/pyLikelihood/python/BinnedAnalysis.py,v 1.1.1.1 2005/08/22 16:19:27 jchiang Exp $
#

import numarray as num
import pyLikelihood as pyLike
from SrcModel import SourceModel
from AnalysisBase import AnalysisBase
from SimpleDialog import SimpleDialog, map, Param

_funcFactory = pyLike.SourceFactory_funcFactory()

class BinnedObs(object):
    def __init__(self, srcMaps=None, expCube=None, binnedExpMap=None,
                 irfs='TEST'):
        if srcMaps is None or expCube is None:
            srcMaps, expCube, binnedExpMap, irfs = self._obsDialog(srcMaps,
                                                                   expCube)
        self._inputs = '\n'.join(('Source maps: ' + str(srcMaps),
                                  'Exposure cube: ' + str(expCube),
                                  'Exposure map: ' + str(binnedExpMap),
                                  'IRFs: ' + str(irfs)))
        self.srcMaps = srcMaps
        self._createObservation(srcMaps, expCube, irfs)
        if binnedExpMap is not None and binnedExpMap != "":
            pyLike.SourceMap_setBinnedExposure(binnedExpMap)
        self.countsMap = pyLike.CountsMap(srcMaps)
    def _createObservation(self, srcMaps, expCube, irfs):
        self._respFuncs = pyLike.ResponseFunctions()
        self._respFuncs.load(irfs)
        self._expMap = pyLike.ExposureMap()
        self._scData = pyLike.ScData()
        self._roiCuts = pyLike.RoiCuts()
        self._roiCuts.readCuts(srcMaps, "", False)
        self._expCube = pyLike.ExposureCube()
        self._expCube.readExposureCube(expCube)
        self._eventCont = pyLike.EventContainer(self._respFuncs,
                                                self._roiCuts,
                                                self._scData)
        self.observation = pyLike.Observation(self._respFuncs, self._scData,
                                              self._roiCuts, self._expCube,
                                              self._expMap, self._eventCont)
    def __getattr__(self, attrname):
        return getattr(self.observation, attrname)
    def __repr__(self):
        return self._inputs
    def _obsDialog(self, srcMaps, expCube):
        paramDict = map()
        if srcMaps is None:
            paramDict['srcMaps'] = Param('file', '*.fits')
        else:
            paramDict['srcMaps'] = Param('file', srcMaps)
        if expCube is None:
            paramDict['expCube'] = Param('file', '*.fits')
        else:
            paramDict['expCube'] = Param('file', expCube)
        paramDict['binnedExpMap'] = Param('file', '')
        paramDict['irfs'] = Param('string', 'TEST')
        root = SimpleDialog(paramDict, title="Binned Analysis Elements:")
        root.mainloop()
        output = (paramDict['srcMaps'].value(),
                  paramDict['expCube'].value(),
                  paramDict['binnedExpMap'].value(),
                  paramDict['irfs'].value())
        return output
        
class BinnedAnalysis(AnalysisBase):
    def __init__(self, binnedData, srcModel=None, optimizer='Minuit'):
        AnalysisBase.__init__(self)
        if srcModel is None:
            srcModel, optimizer = self._srcDialog()
        self._inputs = '\n'.join((str(binnedData),
                                  'Source model file: ' + str(srcModel),
                                  'Optimizer: ' + str(optimizer)))
        self.binnedData = binnedData
        self.srcModel = srcModel
        self.optimizer = optimizer
        self.logLike = pyLike.BinnedLikelihood(binnedData.countsMap,
                                               binnedData.observation,
                                               binnedData.srcMaps,
                                               True)
        self.logLike.readXml(srcModel, _funcFactory, False)
        self.model = SourceModel(self.logLike)
        self.energies = num.array(self.logLike.energies())
        self.e_vals = num.sqrt(self.energies[:-1]*self.energies[1:])
        self.nobs = self.logLike.countsSpectrum();
    def _srcCnts(self, srcName):
        srcMap = self.logLike.sourceMap(srcName)
        npreds = srcMap.npreds()
        src = self.logLike.getSource(srcName)
        cnts = []
        for k in range(len(self.energies)-1):
            emin, emax = self.energies[k:k+2]
            cnts.append(src.pixelCounts(emin, emax, npreds[k], npreds[k+1]))
        return num.array(cnts)