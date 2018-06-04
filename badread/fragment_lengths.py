"""
Copyright 2018 Ryan Wick (rrwick@gmail.com)
https://github.com/rrwick/Badread

This file is part of Badread. Badread is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version. Badread is distributed
in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along with Badread.
If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
import scipy.special
import sys
from .quickhist import quickhist_gamma


class FragmentLengths(object):

    def __init__(self, distribution, mean, stdev, output=sys.stderr):
        self.distribution = distribution
        self.mean = mean
        self.stdev = stdev
        assert distribution == 'constant' or distribution == 'gamma'
        print('', file=output)
        if self.distribution == 'gamma' and self.stdev == 0:
            print('Switching from "gamma" to "constant" read length distribution because '
                  'stdev equals 0', file=output)
            self.distribution = 'constant'
        if self.distribution == 'constant':
            self.gamma_k, self.gamma_t = None, None
            print('Using a constant fragment length of {} bp'.format(mean), file=output)
        else:  # gamma distribution
            print('Generating fragment lengths from a gamma distribution:', file=output)
            gamma_a, gamma_b, self.gamma_k, self.gamma_t = gamma_parameters(mean, stdev)
            print('  k (shape) = ' + '%.4e' % self.gamma_k, file=output)
            print('  theta (scale) = ' + '%.4e' % self.gamma_t, file=output)
            print('  mean: {} bp'.format(mean), file=output)
            print('  stdev: {} bp'.format(stdev), file=output)
            n50 = int(round(find_n_value(gamma_a, gamma_b, 50)))
            print('  theoretical N50: {} bp'.format(n50),
                  file=output)
            quickhist_gamma(self.gamma_k, self.gamma_t, n50, 8)

    def get_fragment_length(self):
        if self.distribution == 'constant':
            return self.mean
        else:  # gamma distribution
            return int(round(np.random.gamma(self.gamma_k, self.gamma_t)))


def gamma_parameters(gamma_mean, gamma_stdev):
    # Shape and rate parametrisation:
    gamma_a = (gamma_mean ** 2) / (gamma_stdev ** 2)
    gamma_b = gamma_mean / (gamma_stdev ** 2)

    # Shape and scale parametrisation:
    gamma_k = (gamma_mean ** 2) / (gamma_stdev ** 2)
    gamma_t = (gamma_stdev ** 2) / gamma_mean

    return gamma_a, gamma_b, gamma_k, gamma_t


def find_n_value(a, b, n):
    target = 1.0 - (n / 100.0)
    bottom_range = 0.0
    top_range = 1.0
    while base_distribution_integral(a, b, top_range) < target:
        bottom_range = top_range
        top_range *= 2
    guess = (bottom_range + top_range) / 2.0
    while True:
        integral = base_distribution_integral(a, b, guess)
        if top_range - bottom_range < 0.01:
            return guess
        if guess == target:
            return guess
        elif integral < target:
            bottom_range = guess
            guess = (bottom_range + top_range) / 2.0
        else:  # integral > target:
            top_range = guess
            guess = (bottom_range + top_range) / 2.0


def base_distribution_integral(a, b, x):
    # TODO: this function bombs out if the value of a is too large.
    #       Could I use log-gamma functions to avoid this, perhaps?
    g = scipy.special.gamma(a+1)
    h = inc_gamma(a+1, b*x)
    return (g - h) / g


def inc_gamma(a, b):
    """
    SciPy seems to define the incomplete Gamma function a bit differently than WolframAlpha (which
    I used to do the calc), so this function should represent a WolframAlpha incomplete Gamma.
    https://stackoverflow.com/questions/38713199/incomplete-gamma-function-in-scipy
    """
    return scipy.special.gamma(a) * (1-scipy.special.gammainc(a, b))