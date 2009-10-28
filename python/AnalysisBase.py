"""
Base class for Likelihood analysis Python modules.

@author J. Chiang <jchiang@slac.stanford.edu>
"""
#
# $Header: /nfs/slac/g/glast/ground/cvs/pyLikelihood/python/AnalysisBase.py,v 1.57 2009/10/28 04:32:52 jchiang Exp $
#

import sys
import numpy as num
import pyLikelihood as pyLike
from SrcModel import SourceModel
try:
    from SimpleDialog import SimpleDialog, map, Param
except ImportError, message:
    print "Caught ImportError: ", message
    pass

_plotter_package = 'root'

class AnalysisBase(object):
    def __init__(self):
        self.maxdist = 20
        self.tol = 1e-3
        self.covariance = None
        self.covar_is_current = False
        self.tolType = pyLike.ABSOLUTE
        self.optObject = None
    def _srcDialog(self):
        paramDict = map()
        paramDict['Source Model File'] = Param('file', '*.xml')
        paramDict['optimizer'] = Param('string', 'Drmngb')
        root = SimpleDialog(paramDict, title="Define Analysis Object:")
        root.mainloop()
        xmlFile = paramDict['Source Model File'].value()
        output = (xmlFile, paramDict['optimizer'].value())
        return output
    def setPlotter(self, plotter='hippo'):
        global _plotter_package
        _plotter_package = plotter
        if plotter == 'hippo':
            import hippoplotter as plot
            return plot
    def __call__(self):
        return -self.logLike.value()
    def setFitTolType(self, tolType):
        if tolType in (pyLike.RELATIVE, pyLike.ABSOLUTE):
            self.tolType = tolType
        else:
            raise RuntimeError("Invalid fit tolerance type. " +
                               "Valid values are 0=RELATIVE or 1=ABSOLUTE")
    def fit(self, verbosity=3, tol=None, optimizer=None,
            covar=False, optObject=None):
        if tol is None:
            tol = self.tol
        errors = self._errors(optimizer, verbosity, tol, covar=covar,
                              optObject=optObject)
        return -self.logLike.value()
    def optimize(self, verbosity=3, tol=None, optimizer=None):
        self.logLike.syncParams()
        if optimizer is None:
            optimizer = self.optimizer
        if tol is None:
            tol = self.tol
        optFactory = pyLike.OptimizerFactory_instance()
        myOpt = optFactory.create(optimizer, self.logLike)
        myOpt.find_min_only(verbosity, tol, self.tolType)
    def _errors(self, optimizer=None, verbosity=0, tol=None,
                useBase=False, covar=False, optObject=None):
        self.logLike.syncParams()
        if optimizer is None:
            optimizer = self.optimizer
        if tol is None:
            tol = self.tol
        if optObject is None:
            optFactory = pyLike.OptimizerFactory_instance()
            myOpt = optFactory.create(optimizer, self.logLike)
        else:
            myOpt = optObject
        self.optObject = myOpt
        myOpt.find_min(verbosity, tol, self.tolType)
        errors = myOpt.getUncertainty(useBase)
        if covar:
            self.covariance = myOpt.covarianceMatrix()
            self.covar_is_current = True
        else:
            self.covar_is_current = False
        j = 0
        for i in range(len(self.model.params)):
            if self.model[i].isFree():
                self.model[i].setError(errors[j])
                j += 1
        return errors
    def minosError(self, *args):
        if len(args) == 1:
            return self._minosIndexError(args[0])
        par_index = self.par_index(args[0], args[1])
        return self._minosIndexError(par_index)
    def par_index(self, srcName, parName):
        source_names = self.sourceNames()
        par_index = -1
        for src in source_names:
            pars = pyLike.ParameterVector()
            self[src].src.spectrum().getParams(pars)
            for par in pars:
                par_index += 1
                if src == srcName and par.getName() == parName:
                    return par_index
        raise RuntimeError("Parameter %s for source %s not found."
                           % (parName, srcName))
    def _minosIndexError(self, par_index):
        if self.optObject is None:
            raise RuntimeError("To evaluate minos errors, a fit must first be "
                               + "performed using the Minuit or NewMinuit "
                               + "optimizers.")
        freeParams = pyLike.DoubleVector()
        self.logLike.getFreeParamValues(freeParams)
        pars = self.params()
        if par_index not in range(len(pars)):
            raise RuntimeError("Invalid model parameter index.")
        free_indices = {}
        ii = -1
        for i, par in enumerate(pars):
            if par.isFree():
                ii += 1
                free_indices[i] = ii
        if par_index not in free_indices.keys():
            raise RuntimeError("Cannot evaluate minos errors for a frozen "
                               + "parameter.")
        try:
            errors = self.optObject.Minos(free_indices[par_index])
            self.logLike.setFreeParamValues(freeParams)
            return errors
        except RuntimeError, message:
            print "Minos error encountered for parameter %i." % par_index
            print "Attempting to reset free parameters."
            self.thaw(par_index)
            self.logLike.setFreeParamValues(freeParams)
            raise RuntimeError(message)
    def getExtraSourceAttributes(self):
        source_attributes = {}
        for src in self.model.srcNames:
            source_attributes[src] = {}
            for key in self.model[src].__dict__.keys():
                if key not in ('funcs', 'src'):
                    source_attributes[src][key] = self.model[src].__dict__[key]
        return source_attributes
    def Ts(self, srcName, reoptimize=False, approx=True,
           tol=None, MaxIterations=10, verbosity=0):
        if verbosity > 0:
            print "*** Start Ts_dl ***"
        source_attributes = self.getExtraSourceAttributes()
        self.logLike.syncParams()
        src = self.logLike.getSource(srcName)
        freeParams = pyLike.DoubleVector()
        self.logLike.getFreeParamValues(freeParams)
        logLike1 = self.logLike.value()
        self._ts_src = self.logLike.deleteSource(srcName)
        logLike0 = self.logLike.value()
        if tol is None:
            tol = self.tol
        if reoptimize:
            if verbosity > 0:
                print "** Do reoptimize"
            optFactory = pyLike.OptimizerFactory_instance()
            myOpt = optFactory.create(self.optimizer, self.logLike)
            Niter = 1
            while Niter <= MaxIterations:
                try:
                    myOpt.find_min(0, tol)
                    break
                except RuntimeError,e:
                    print e
                if verbosity > 0:
                    print "** Iteration :",Niter
                Niter += 1
        else:
            if approx:
                try:
                    self._renorm()
                except ZeroDivisionError:
                    pass
        self.logLike.syncParams()
        logLike0 = max(self.logLike.value(), logLike0)
        Ts_value = 2*(logLike1 - logLike0)
        self.logLike.addSource(self._ts_src)
        self.logLike.setFreeParamValues(freeParams)
        self.model = SourceModel(self.logLike)
        for src in source_attributes:
            self.model[src].__dict__.update(source_attributes[src])
        return Ts_value
    def Ts_old(self, srcName, reoptimize=False, approx=True, tol=None):
        source_attributes = self.getExtraSourceAttributes()
        self.logLike.syncParams()
        src = self.logLike.getSource(srcName)
        freeParams = pyLike.DoubleVector()
        self.logLike.getFreeParamValues(freeParams)
        logLike1 = self.logLike.value()
        self._ts_src = self.logLike.deleteSource(srcName)
        logLike0 = self.logLike.value()
        if tol is None:
            tol = self.tol
        if reoptimize:
            optFactory = pyLike.OptimizerFactory_instance()
            myOpt = optFactory.create(self.optimizer, self.logLike)
            myOpt.find_min_only(0, tol, self.tolType)
        else:
            if approx:
                try:
                    self._renorm()
                except ZeroDivisionError:
                    pass
        self.logLike.syncParams()
        logLike0 = max(self.logLike.value(), logLike0)
        Ts_value = 2*(logLike1 - logLike0)
        self.logLike.addSource(self._ts_src)
        self.logLike.setFreeParamValues(freeParams)
        self.model = SourceModel(self.logLike)
        #
        # reset the extra source attributes, if any
        #
        for src in source_attributes:
            self.model[src].__dict__.update(source_attributes[src])
        return Ts_value
    def flux(self, srcName, emin=100, emax=3e5, energyFlux=False):
        if energyFlux:
            return self[srcName].energyFlux(emin, emax)
        else:
            return self[srcName].flux(emin, emax)
    def energyFlux(self, srcName, emin=100, emax=3e5):
        return self.flux(srcName, emin, emax, True)
    def energyFluxError(self, srcName, emin=100, emax=3e5, npts=1000):
        return self.fluxError(srcName, emin, emax, True, npts)
    def fluxError(self, srcName, emin=100, emax=3e5, energyFlux=False,
                  npts=1000):
        par_index_map = {}
        indx = 0
        for src in self.sourceNames():
            parNames = pyLike.StringVector()
            self[src].src.spectrum().getFreeParamNames(parNames)
            for par in parNames:
                par_index_map["::".join((src, par))] = indx
                indx += 1
        #
        # Build the source-specific covariance matrix.
        #
        if self.covariance is None:
            raise RuntimeError("Covariance matrix has not been computed.")
        if not self.covar_is_current:
            sys.stderr.write("Warning: covariance matrix has not been " +
                             "updated in the most recent fit.\n")
        covar = num.array(self.covariance)
        if len(covar) != len(par_index_map):
            raise RuntimeError("Covariance matrix size does not match the " +
                               "number of free parameters.")
        my_covar = []
        srcpars = pyLike.StringVector()
        self[srcName].src.spectrum().getFreeParamNames(srcpars)
        pars = ["::".join((srcName, x)) for x in srcpars]
        for xpar in pars:
            ix = par_index_map[xpar]
            my_covar.append([covar[ix][par_index_map[ypar]] for ypar in pars])
        my_covar = num.array(my_covar)

        if energyFlux:
            partials = num.array([self[srcName].energyFluxDeriv(x, emin,
                                                                emax, npts) 
                                  for x in srcpars])
        else:
            partials = num.array([self[srcName].fluxDeriv(x, emin, emax, npts) 
                                  for x in srcpars])

        return num.sqrt(num.dot(partials, num.dot(my_covar, partials)))
    def deleteSource(self, srcName):
        source_attributes = self.getExtraSourceAttributes()
        src = self.logLike.deleteSource(srcName)
        self.model = SourceModel(self.logLike)
        #
        # reset the remaining extra source attributes
        #
        for item in source_attributes:
            if self.model[item] is not None:
                self.model[item].__dict__.update(source_attributes[item])
        return src
    def addSource(self, src):
        source_attributes = self.getExtraSourceAttributes()
        self.logLike.addSource(src)
        self.model = SourceModel(self.logLike)
        for item in source_attributes:
            if self.model[item] is not None:
                self.model[item].__dict__.update(source_attributes[item])
    def writeCountsSpectra(self, outfile='counts_spectra.fits'):
        counts = pyLike.CountsSpectra(self.logLike)
        try:
            emin, emax = self.observation.observation.roiCuts().getEnergyCuts()
            counts.setEbounds(emin, emax, 21)
        except:
            pass
        counts.writeTable(outfile)
    def _renorm(self, factor=None):
        if factor is None:
            freeNpred, totalNpred = self._npredValues()
            deficit = sum(self.nobs) - totalNpred
            self.renormFactor = 1. + deficit/freeNpred
        else:
            self.renormFactor = factor
        if self.renormFactor < 1:
            self.renormFactor = 1
        srcNames = self.sourceNames()
        for src in srcNames:
            parameter = self.normPar(src)
            if parameter.isFree() and self._isDiffuseOrNearby(src):
                oldValue = parameter.getValue()
                newValue = oldValue*self.renormFactor
                # ensure new value is within parameter bounds
                xmin, xmax = parameter.getBounds()
                if xmin <= newValue and newValue <= xmax:
                    parameter.setValue(newValue)
    def _npredValues(self):
        srcNames = self.sourceNames()
        freeNpred = 0
        totalNpred = 0
        for src in srcNames:
            npred = self.logLike.NpredValue(src)
            totalNpred += npred
            if self.normPar(src).isFree() and self._isDiffuseOrNearby(src):
                freeNpred += npred
        return freeNpred, totalNpred
    def _isDiffuseOrNearby(self, srcName):
        if (self[srcName].src.getType() == 'Diffuse' or 
            self._ts_src.getType() == 'Diffuse'):
            return True
        elif self._separation(self._ts_src, self[srcName].src) < self.maxdist:
            return True
        return False
    def _separation(self, src1, src2):
        dir1 = pyLike.PointSource_cast(src1).getDir()
        dir2 = pyLike.PointSource_cast(src2).getDir()
        return dir1.difference(dir2)*180./num.pi
    def saveCurrentFit(self):
        self.logLike.saveCurrentFit()
    def restoreBestFit(self):
        self.logLike.restoreBestFit()
    def NpredValue(self, src):
        return self.logLike.NpredValue(src)
    def total_nobs(self):
        return sum(self.nobs)
    def syncSrcParams(self, src=None):
        if src is not None:
            self.logLike.syncSrcParams(src)
        else:
            for src in self.sourceNames():
                self.logLike.syncSrcParams(src)
    def sourceNames(self):
        srcNames = pyLike.StringVector()
        self.logLike.getSrcNames(srcNames)
        return tuple(srcNames)
    def oplot(self, color=None):
        self.plot(oplot=1, color=color)
    def _importPlotter(self):
        if _plotter_package == 'root':
            from RootPlot import RootPlot
            self.plotter = RootPlot
        elif _plotter_package == 'hippo':
            from HippoPlot import HippoPlot
            self.plotter = HippoPlot
    def plot(self, oplot=0, color=None, omit=(), symbol='line'):
        try:
            self._importPlotter()
        except ImportError:
            raise RuntimeError, ("Sorry plotting is not available using %s.\n"
                                 % _plotter_package +
                                 "Use setPlotter to try a different plotter")
        if oplot == 0:
            self.spectralPlot = self._plotData()
            if color is None:
                color = 'black'
        else:
            if color is None:
                color = 'red'
        srcNames = self.sourceNames()
        total_counts = None
        for src in srcNames:
            if total_counts is None:
                total_counts = self._plotSource(src, color=color, 
                                                show=(src not in omit))
            else:
                total_counts += self._plotSource(src, color=color, 
                                                 show=(src not in omit))
        self.spectralPlot.overlay(self.e_vals, total_counts, color=color,
                                  symbol=symbol)
        self._plotResiduals(total_counts, oplot=oplot, color=color)
    def _plotResiduals(self, model, oplot=0, color='black'):
        resid = (self.nobs - model)/model
        resid_err = num.sqrt(self.nobs)/model
        if oplot and hasattr(self, 'residualPlot'):
            self.residualPlot.overlay(self.e_vals, resid, dy=resid_err,
                                      color=color, symbol='plus')
        else:
            self.residualPlot = self.plotter(self.e_vals, resid, dy=resid_err,
                                             xtitle='Energy (MeV)',
                                             ytitle='(counts - model)/model',
                                             xlog=1, color=color,
                                             symbol='plus')
            zeros = num.zeros(len(self.e_vals))
            self.residualPlot.overlay(self.e_vals, zeros, symbol='dotted')
    def _plotData(self):
        energies = self.e_vals
        my_plot = self.plotter(energies, self.nobs, dy=num.sqrt(self.nobs),
                               xlog=1, ylog=1, xtitle='Energy (MeV)',
                               ytitle='counts / bin')
        return my_plot
    def _plotSource(self, srcName, color='black', symbol='line', show=True):
        energies = self.e_vals

        model_counts = self._srcCnts(srcName)

        if show:
            try:
                self.spectralPlot.overlay(energies, model_counts, color=color,
                                          symbol=symbol)
            except AttributeError:
                self.spectralPlot = self.plotter(energies, model_counts, xlog=1,
                                                 ylog=1, xtitle='Energy (MeV)',
                                                 ytitle='counts spectrum',
                                                 color=color, symbol=symbol)
        return model_counts
    def plotSource(self, srcName, color='black',symbol='line'):
        self._plotSource(srcName, color, symbol)
    def __repr__(self):
        return self._inputs()
    def __getitem__(self, name):
        return self.model[name]
    def __setitem__(self, name, value):
        self.model[name] = value
        self.logLike.syncSrcParams(self.model[name].srcName)
    def normPar(self, srcName):
        return self[srcName].funcs['Spectrum'].normPar()
    def freePars(self, srcName):
        pars = pyLike.ParameterVector()
        self[srcName].funcs['Spectrum'].getFreeParams(pars)
        return pars
    def setFreeFlag(self, srcName, pars, value):
        src_spectrum = self[srcName].funcs['Spectrum']
        for item in pars:
            src_spectrum.parameter(item.getName()).setFree(value)
    def params(self):
        return self.model.params
    def thaw(self, i):
        try:
            for ii in i:
                self.model[ii].setFree(1)
        except TypeError:
            self.model[i].setFree(1)
    def freeze(self, i):
        try:
            for ii in i:
                self.model[ii].setFree(0)
        except TypeError:
            self.model[i].setFree(0)
    def writeXml(self, xmlFile=None):
        if xmlFile is None:
            xmlFile = self.srcModel
        self.logLike.writeXml(xmlFile)
        self.srcModel = xmlFile

def _quotefn(filename):
    if filename is None:
        return None
    else:
        return "'" + filename + "'"

def _null_file(filename):
    if filename == 'none' or filename == '':
        return None
    else:
        return filename
