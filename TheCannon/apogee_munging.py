from __future__ import (absolute_import, division, print_function,)
import numpy as np
import scipy.optimize as opt
import os
import sys
from cannon.helpers import Table
from cannon.dataset import DataFrame
import matplotlib.pyplot as plt

# python 3 special
PY3 = sys.version_info[0] > 2
if not PY3:
    range = xrange

try:
    from astropy.io import fits as pyfits
except ImportError:
    import pyfits

class ApogeeDF(DataFrame):
    """ DataFrame for keeping APOGEE data organized. 
    
    Performs the APOGEE Munging necessary for making the data "Cannonizable." 
    Retrieves the data (assumse already in rest frame), creates and reads bad-
    pixel mask, builds inverse variance vectors, packages them all into 
    rectangular blocks.
    """
   
    def __init__(self, training_dir, test_dir, label_file):
        super(self.__class__, self).__init__(training_dir, test_dir, label_file)
        # we discard the edges of the fluxes: 10 A, corresponding to ~50 pix
        self.ranges = [[371,3192], [3697,5997], [6461,8255]]

    def get_pixmask(fluxes, flux_errs):
        """ Return a mask array of bad pixels

        Bad pixels are defined as follows: fluxes or errors are not finite, or 
        reported errors are negative.

        Parameters
        ----------
        fluxes: ndarray
            flux array

        flux_errs: ndarray
            measurement uncertainties on fluxes

        Returns
        -------
        mask: ndarray, dtype=bool
            array giving bad pixels as True values
        """
        bad_flux = (~np.isfinite(fluxes)) | (fluxes == 0)   
        bad_err = (~np.isfinite(flux_errs)) | (flux_errs <= 0)
        bad_pix = bad_err | bad_flux

        return bad_pix

    def get_spectra(self, *args, **kwargs):
        """
        Extracts spectra (wavelengths, fluxes, fluxerrs) from apogee fits files

        Returns
        -------
        lambdas: numpy ndarray of length npixels
            rest-frame wavelength vector

        fluxes: numpy ndarray of shape (nstars, npixels)
            training set or test set pixel intensities

        ivars: numpy ndarray of shape (nstars, npixels)
            inverse variances, parallel to fluxes

        SNRs: numpy ndarray of length nstars
        """
        files = [self.spec_dir + "/" + filename
                 for filename in os.listdir(self.spec_dir)]
        files = list(sorted(files))  
        LARGE = kwargs.get('large', 1000000.)
        nstars = len(files)  
        
        for jj, fits_file in enumerate(files):
            file_in = pyfits.open(fits_file)
            flux = np.array(file_in[1].data)
            if jj == 0:
                npixels = len(flux)
                SNRs = np.zeros(nstars, dtype=float)   
                fluxes = np.zeros((nstars, npixels), dtype=float)
                flux_errs = np.zeros(fluxes.shape, dtype=float) 
                ivars = np.zeros(fluxes.shape, dtype=float)
                start_wl = file_in[1].header['CRVAL1']
                diff_wl = file_in[1].header['CDELT1']
                val = diff_wl * (npixels) + start_wl
                wl_full_log = np.arange(start_wl,val, diff_wl)
                wl_full = [10 ** aval for aval in wl_full_log]
                lambdas = np.array(wl_full)
            flux_err = np.array((file_in[2].data))
            badpix = get_pixmask(flux, flux_err)
            flux = np.ma.array(flux, mask=badpix, fill_value=0.)
            flux_err = np.ma.array(flux_err, mask=badpix, fill_value=LARGE)
            SNRs[jj] = np.ma.median(flux/flux_err)
            ones = np.ma.array(np.ones(npixels), mask=badpix)
            flux = np.ma.filled(flux)
            flux_err = np.ma.filled(flux_err)
            ivar = ones / (flux_err**2)
            ivar = np.ma.filled(ivar, fill_value=0.)
            fluxes[jj,:] = flux
            flux_errs[jj,:] = flux_err
            ivars[jj,:] = ivar

        return lambdas, fluxes, ivars, SNRs

    def get_reference_labels(self, *args, **kwags):
        """Extracts training labels from file.

        Assumes that first row is # then label names, that first column is # 
        then the filenames, that the remaining values are floats and that 
        user wants all of the labels. User can pick specific labels later.

        Returns
        -------
        data['id']: 
        label_names: list of label names
        data: np ndarray of size (nstars, nlabels)
            label values
        """
        data = Table(self.label_file)
        data.sort('id')
        label_names = data.keys()
        nlabels = len(label_names)

        print("Loaded stellar IDs, format: %s" % data['id'][0])
        print("Loaded %d labels:" % nlabels)
        print(label_names)
        return data['id'], label_names, data
