# Licensed under a 3-clause BSD style license - see LICENSE.rst
import pytest
from numpy.testing import assert_allclose
import astropy.units as u
import numpy as np
from ...utils.testing import requires_data, requires_dependency
from ...utils.random import get_random_state
from ...irf import EffectiveAreaTable, EnergyDispersion
from ...utils.fitting import Fit
from ..models import PowerLaw, ConstantModel
from ...spectrum import (
    PHACountsSpectrum,
    ONOFFSpectrumDataset
)



class Test_ONOFFSpectrumDataset:
    """ Test ON OFF SpectrumDataset"""
    def setup(self):

        etrue = np.logspace(-1,1,10)*u.TeV
        self.e_true = etrue
        ereco = np.logspace(-1,1,5)*u.TeV
        elo = ereco[:-1]
        ehi = ereco[1:]

        self.aeff = EffectiveAreaTable(etrue[:-1],etrue[1:], np.ones(9)*u.cm**2)
        self.edisp = EnergyDispersion.from_diagonal_response(etrue, ereco)

        self.on_counts = PHACountsSpectrum(elo, ehi, np.ones_like(elo), backscal=np.ones_like(elo))
        self.off_counts = PHACountsSpectrum(elo, ehi, np.ones_like(elo)*10, backscal=np.ones_like(elo)*10)

        self.livetime = 1000*u.s

    def test_init_no_model(self):
        dataset = ONOFFSpectrumDataset(ONcounts=self.on_counts, OFFcounts=self.off_counts,
                         aeff=self.aeff, edisp=self.edisp, livetime = self.livetime)

        with pytest.raises(AttributeError):
            dataset.npred()

    def test_alpha(self):
        dataset = ONOFFSpectrumDataset(ONcounts=self.on_counts, OFFcounts=self.off_counts,
                         aeff=self.aeff, edisp=self.edisp, livetime = self.livetime)

        assert dataset.alpha.shape == (4,)
        assert_allclose(dataset.alpha, 0.1)

    def test_npred_no_edisp(self):
        const = 1 / u.TeV / u.cm ** 2 / u.s
        model = ConstantModel(const)
        livetime = 1*u.s
        dataset = ONOFFSpectrumDataset(ONcounts=self.on_counts, OFFcounts=self.off_counts,
                         aeff=self.aeff, model=model, livetime = livetime)

        expected = self.aeff.data.data[0]*(self.aeff.energy.hi[-1]-self.aeff.energy.lo[0])*const*livetime

        assert_allclose(dataset.npred().sum(), expected.value)

@requires_dependency("iminuit")
class TestFit:
    """Test fit on counts spectra without any IRFs"""

    def setup(self):
        self.nbins = 30
        binning = np.logspace(-1, 1, self.nbins + 1) * u.TeV
        self.source_model = PowerLaw(
            index=2, amplitude=1e5 / u.TeV, reference=0.1 * u.TeV
        )
        self.bkg_model = PowerLaw(
            index=3, amplitude=1e4 / u.TeV, reference=0.1 * u.TeV
        )

        self.alpha = 0.1
        random_state = get_random_state(23)
        npred = self.source_model.integral(binning[:-1], binning[1:])
        source_counts = random_state.poisson(npred)
        self.src = PHACountsSpectrum(
            energy_lo=binning[:-1],
            energy_hi=binning[1:],
            data=source_counts,
            backscal=1,
        )
        # Currently it's necessary to specify a lifetime
        self.src.livetime = 1 * u.s

        npred_bkg = self.bkg_model.integral(binning[:-1], binning[1:])

        bkg_counts = random_state.poisson(npred_bkg)
        off_counts = random_state.poisson(npred_bkg * 1.0 / self.alpha)
        self.bkg = PHACountsSpectrum(
            energy_lo=binning[:-1], energy_hi=binning[1:], data=bkg_counts
        )
        self.off = PHACountsSpectrum(
            energy_lo=binning[:-1],
            energy_hi=binning[1:],
            data=off_counts,
            backscal=1.0 / self.alpha,
        )


    def test_wstat(self):
        """WStat with on source and background spectrum"""
        on_vector = self.src.copy()
        on_vector.data.data += self.bkg.data.data
        obs = ONOFFSpectrumDataset(ONcounts=on_vector, OFFcounts=self.off)
        obs.model = self.source_model

        self.source_model.parameters.index = 1.12

        fit = Fit(obs)
        result = fit.run()
        pars = self.source_model.parameters

        assert_allclose(pars["index"].value, 1.997342, rtol=1e-3)
        assert_allclose(pars["amplitude"].value, 100245.187067, rtol=1e-3)
        assert_allclose(result.total_stat, 30.022316, rtol=1e-3)

    def test_joint(self):
        """Test joint fit for obs with different energy binning"""
        on_vector = self.src.copy()
        on_vector.data.data += self.bkg.data.data
        obs1 = ONOFFSpectrumDataset(ONcounts=on_vector, OFFcounts=self.off)
        obs1.model = self.source_model

        src_rebinned = self.src.rebin(2)
        bkg_rebinned = self.off.rebin(2)
        src_rebinned.data.data += self.bkg.rebin(2).data.data

        obs2 = ONOFFSpectrumDataset(ONcounts=src_rebinned, OFFcounts=bkg_rebinned)
        obs2.model = self.source_model

        fit = Fit([obs1, obs2])
        result = fit.run()
        pars = self.source_model.parameters
        assert_allclose(pars["index"].value, 1.996456, rtol=1e-3)

