# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Helper functions to work with distributions."""
import numpy as np
from .utils import get_random_state


#__all__ = [
#    "normalize",
#    "density",
#    "draw",
#    "pdf",
#    "get_random_state",
#    "sample_sphere",
#    "sample_sphere_distance",
#    "sample_powerlaw",
#]


class InverseCDFSampler:
    """Inverse CDF sampler.
        
        Parameters
        ----------
        pdf : `~`gammapy.maps.Map`
        predicted source counts
        
        """
    def __init__(self, pdf, axis=None, random_state=0):
        """Determines a set of random numbers and calculate the cumulative distribution function"""
        self.random_state = get_random_state(random_state)
        self.axis = axis
        
        if axis is not None:
            self.cdf = np.cumsum(pdf, axis=self.axis)
            self.cdf /= self.cdf[:, [-1]]
        else:
            self.pdf_shape = pdf.shape  #gives the shape of the PDF array
            
            pdf = pdf.ravel() / pdf.sum()  #flattens the array along one axis
            self.sortindex = np.argsort(pdf, axis=None) #sorting of the elements and giving the indexes
            
            self.pdf = pdf[self.sortindex]  #sort the pdf array
            self.cdf = np.cumsum(self.pdf)  #evaluate the cumulative sum of the PDF array

    def sample_axis(self):
        """Sample along a given axis.
        """
        choice = self.random_state.uniform(high=1, size=len(self.cdf))

        #find the indices corresponding to this point on the CDF
        index = np.argmin(np.abs(choice.reshape(-1, 1) - self.cdf), axis=self.axis)

        return index + self.random_state.uniform(low=-0.5, high=0.5,
                 size=len(self.cdf))

    def sample(self, size):
        """Draw sample from the given PDF.

        Parameters
        ----------
        size : int
        Number of samples to draw.

        Returns
        -------
        index : tuple of `~numpy.ndarray`
        Coordinates of the drawn sample
        """
        #pick numbers which are uniformly random over the cumulative distribution function
        choice = self.random_state.uniform(high=1, size=size)

        #find the indices corresponding to this point on the CDF
        index = np.searchsorted(self.cdf, choice)
        index = self.sortindex[index]

        # map back to multi-dimensional indexing
        index = np.unravel_index(index, self.pdf_shape) 
        index = np.vstack(index)

        index = index + self.random_state.uniform(low=-0.5, high=0.5,
                                              size=index.shape)
        return index
