#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
STPPG: Spatio-Temporal Point Process Generator

References:
- https://www.jstatsoft.org/article/view/v053i02
- https://www.ism.ac.jp/editsec/aism/pdf/044_1_0001.pdf
- https://github.com/meowoodie/Spatio-Temporal-Point-Process-Simulator

Dependencies:
- Python 3.6.7
"""

import sys
import utils
import arrow
import numpy as np
from scipy.stats import norm
from itertools import product
import matplotlib.pyplot as plt

class StdDiffusionKernel(object):
    """
    Kernel function including the diffusion-type model proposed by Musmeci and
    Vere-Jones (1992).
    """
    def __init__(self, C=1., beta=1., sigma_x=1., sigma_y=1.):
        self.C       = C
        self.beta    = beta
        self.sigma_x = sigma_x
        self.sigma_y = sigma_y

    def nu(self, t, s, his_t, his_s):
        delta_s = s - his_s
        delta_t = t - his_t
        delta_x = delta_s[:, 0]
        delta_y = delta_s[:, 1]
        return np.exp(- self.beta * delta_t) * \
            (self.C / (2 * np.pi * self.sigma_x * self.sigma_y * delta_t)) * \
            np.exp((- 1. / (2 * delta_t)) * \
                ((np.square(delta_x) / np.square(self.sigma_x)) + \
                (np.square(delta_y) / np.square(self.sigma_y))))



class GaussianDiffusionKernel(object):
    """
    A Gaussian diffusion kernel function based on the standard kernel function proposed 
    by Musmeci and Vere-Jones (1992). The angle and shape of diffusion ellipse is able  
    to vary according to the location.  
    """
    def __init__(self, mu_x=0., mu_y=0., sigma_x=1., sigma_y=1., rho=0., beta=1., C=1.):
        # kernel parameters
        self.C                     = C # kernel constant
        self.beta                  = beta
        self.mu_x, self.mu_y       = mu_x, mu_y 
        self.sigma_x, self.sigma_y = sigma_x, sigma_y
        self.rho                   = rho

    def nu(self, t, s, his_t, his_s):
        delta_s = s - his_s
        delta_t = t - his_t
        delta_x = delta_s[:, 0]
        delta_y = delta_s[:, 1]
        gaussian_val = np.exp(- self.beta * delta_t) * \
            (self.C / (2 * np.pi * self.sigma_x * self.sigma_y * delta_t * np.sqrt(1 - np.square(self.rho)))) * \
            np.exp((- 1. / (2 * delta_t * (1 - np.square(self.rho)))) * \
                ((np.square(delta_x - self.mu_x) / np.square(self.sigma_x)) + \
                (np.square(delta_y - self.mu_y) / np.square(self.sigma_y)) - \
                (2 * self.rho * (delta_x - self.mu_x) * (delta_y - self.mu_y) / (self.sigma_x * self.sigma_y))))
        return gaussian_val

        

class GaussianMixtureDiffusionKernel(object):
    """
    A Gaussian mixture diffusion kernel function is superposed by multiple Gaussian diffusion 
    kernel function. The number of the Gaussian components is specified by n_comp. 
    """
    def __init__(self, n_comp, w, mu_x, mu_y, sigma_x, sigma_y, rho, beta=1., C=1.):
        self.gdks   = []     # Gaussian components
        self.n_comp = n_comp # number of Gaussian components
        self.w      = w      # weighting vectors for Gaussian components
        # Gaussian mixture component initialization
        for k in range(self.n_comp):
            gdk = GaussianDiffusionKernel(
                mu_x=mu_x[k], mu_y=mu_y[k], sigma_x=sigma_x[k], sigma_y=sigma_y[k], rho=rho[k], beta=beta, C=C)
            self.gdks.append(gdk)
    
    def nu(self, t, s, his_t, his_s):
        nu = 0
        for k in range(self.n_comp):
            nu += self.w[k] * self.gdks[k].nu(t, s, his_t, his_s)
        return nu



class SpatialVariantGaussianDiffusionKernel(object):
    """
    Spatial Variant Gaussian diffusion kernel function
    """
    def __init__(self, 
        f_mu_x=lambda x, y: 0., f_mu_y=lambda x, y: 0., 
        f_sigma_x=lambda x, y: 1., f_sigma_y=lambda x, y: 1., 
        f_rho=lambda x, y: 0., beta=1., C=1.):
        # kernel parameters
        self.C                     = C # kernel constant
        self.beta                  = beta
        self.mu_x, self.mu_y       = f_mu_x, f_mu_y 
        self.sigma_x, self.sigma_y = f_sigma_x, f_sigma_y
        self.rho                   = f_rho

    def nu(self, t, s, his_t, his_s):
        delta_s = s - his_s
        delta_t = t - his_t
        delta_x = delta_s[:, 0]
        delta_y = delta_s[:, 1]
        mu_xs, mu_ys, sigma_xs, sigma_ys, rhos = \
            self.mu_x(his_s[:,0], his_s[:,1]),\
            self.mu_y(his_s[:,0], his_s[:,1]),\
            self.sigma_x(his_s[:,0], his_s[:,1]),\
            self.sigma_y(his_s[:,0], his_s[:,1]),\
            self.rho(his_s[:,0], his_s[:,1])
        gaussian_val = np.exp(- self.beta * delta_t) * \
            (self.C / (2 * np.pi * sigma_xs * sigma_ys * delta_t * np.sqrt(1 - np.square(rhos)))) * \
            np.exp((- 1. / (2 * delta_t * (1 - np.square(rhos)))) * \
                ((np.square(delta_x - mu_xs) / np.square(sigma_xs)) + \
                (np.square(delta_y - mu_ys) / np.square(sigma_ys)) - \
                (2 * rhos * (delta_x - mu_xs) * (delta_y - mu_ys) / (sigma_xs * sigma_ys))))
        return gaussian_val



class SpatialVariantGaussianMixtureDiffusionKernel(object):
    """
    Spatial Variant Gaussian mixture diffusion kernel function
    """
    def __init__(self, n_comp, w, f_mu_x, f_mu_y, f_sigma_x, f_sigma_y, f_rho, beta=1., C=1.):
        # kernel parameters
        self.gdks   = []     # Gaussian components
        self.n_comp = n_comp # number of Gaussian components
        self.w      = w      # weighting vectors for Gaussian components
        # Gaussian mixture component initialization
        for k in range(self.n_comp):
            gdk = SpatialVariantGaussianDiffusionKernel(
                f_mu_x=f_mu_x[k], f_mu_y=f_mu_y[k], 
                f_sigma_x=f_sigma_x[k], f_sigma_y=f_sigma_y[k], 
                f_rho=f_rho[k], beta=beta, C=C)
            self.gdks.append(gdk)

    def nu(self, t, s, his_t, his_s):
        nu = 0
        for k in range(self.n_comp):
            nu += self.w[k] * self.gdks[k].nu(t, s, his_t, his_s)
        return nu



class HawkesLam(object):
    """Intensity of Spatio-temporal Hawkes point process"""
    def __init__(self, mu, kernel, maximum=1e+4):
        self.mu      = mu
        self.kernel  = kernel
        self.maximum = maximum

    def value(self, t, his_t, s, his_s):
        """
        return the intensity value at (t, s).
        The last element of seq_t and seq_s is the location (t, s) that we are
        going to inspect. Prior to that are the past locations which have
        occurred.
        """
        if len(his_t) > 0:
            val = self.mu + np.sum(self.kernel.nu(t, s, his_t, his_s))
        else:
            val = self.mu
        return val

    def upper_bound(self):
        """return the upper bound of the intensity value"""
        return self.maximum

    def __str__(self):
        return "Hawkes processes"

class SpatialTemporalPointProcess(object):
    """
    Marked Spatial Temporal Hawkes Process

    A stochastic spatial temporal points generator based on Hawkes process.
    """

    def __init__(self, lam):
        """
        Params:
        """
        # model parameters
        self.lam     = lam

    def _homogeneous_poisson_sampling(self, T=[0, 1], S=[[0, 1], [0, 1]]):
        """
        To generate a homogeneous Poisson point pattern in space S X T, it basically
        takes two steps:
        1. Simulate the number of events n = N(S) occurring in S according to a
        Poisson distribution with mean lam * |S X T|.
        2. Sample each of the n location according to a uniform distribution on S
        respectively.

        Args:
            lam: intensity (or maximum intensity when used by thining algorithm)
            S:   [(min_t, max_t), (min_x, max_x), (min_y, max_y), ...] indicates the
                range of coordinates regarding a square (or cubic ...) region.
        Returns:
            samples: point process samples:
            [(t1, x1, y1), (t2, x2, y2), ..., (tn, xn, yn)]
        """
        _S     = [T] + S
        # sample the number of events from S
        n      = utils.lebesgue_measure(_S)
        N      = np.random.poisson(size=1, lam=self.lam.upper_bound() * n)
        # simulate spatial sequence and temporal sequence separately.
        points = [ np.random.uniform(_S[i][0], _S[i][1], N) for i in range(len(_S)) ]
        points = np.array(points).transpose()
        # sort the sequence regarding the ascending order of the temporal sample.
        points = points[points[:, 0].argsort()]
        return points

    def _inhomogeneous_poisson_thinning(self, homo_points, verbose):
        """
        To generate a realization of an inhomogeneous Poisson process in S × T, this
        function uses a thining algorithm as follows. For a given intensity function
        lam(s, t):
        1. Define an upper bound max_lam for the intensity function lam(s, t)
        2. Simulate a homogeneous Poisson process with intensity max_lam.
        3. "Thin" the simulated process as follows,
            a. Compute p = lam(s, t)/max_lam for each point (s, t) of the homogeneous
            Poisson process
            b. Generate a sample u from the uniform distribution on (0, 1)
            c. Retain the locations for which u <= p.
        """
        retained_points = np.empty((0, homo_points.shape[1]))
        if verbose:
            print("[%s] generate %s samples from homogeneous poisson point process" % \
                (arrow.now(), homo_points.shape), file=sys.stderr)
        # thining samples by acceptance rate.
        for i in range(homo_points.shape[0]):
            # current time, location and generated historical times and locations.
            t     = homo_points[i, 0]
            s     = homo_points[i, 1:]
            his_t = retained_points[:, 0]
            his_s = retained_points[:, 1:]
            # thinning
            lam_value = self.lam.value(t, his_t, s, his_s)
            lam_bar   = self.lam.upper_bound()
            D         = np.random.uniform()
            # - if lam_value is greater than lam_bar, then skip the generation process
            #   and return None.
            if lam_value > lam_bar:
                print("intensity %f is greater than upper bound %f." % (lam_value, lam_bar), file=sys.stderr)
                return None
            # accept
            if lam_value >= D * lam_bar:
                # retained_points.append(homo_points[i])
                retained_points = np.concatenate([retained_points, homo_points[[i], :]], axis=0)
            # monitor the process of the generation
            if verbose and i != 0 and i % int(homo_points.shape[0] / 10) == 0:
                print("[%s] %d raw samples have been checked. %d samples have been retained." % \
                    (arrow.now(), i, retained_points.shape[0]), file=sys.stderr)
        # log the final results of the thinning algorithm
        if verbose:
            print("[%s] thining samples %s based on %s." % \
                (arrow.now(), retained_points.shape, self.lam), file=sys.stderr)
        return retained_points

    def generate(self, T=[0, 1], S=[[0, 1], [0, 1]], batch_size=10, min_n_points=5, verbose=True):
        """
        generate spatio-temporal points given lambda and kernel function
        """
        points_list = []
        sizes       = []
        max_len     = 0
        b           = 0
        # generate inhomogeneous poisson points iterately
        while b < batch_size:
            homo_points = self._homogeneous_poisson_sampling(T, S)
            points      = self._inhomogeneous_poisson_thinning(homo_points, verbose)
            if points is None or len(points) < min_n_points:
                continue
            max_len = points.shape[0] if max_len < points.shape[0] else max_len
            points_list.append(points)
            sizes.append(len(points))
            print("[%s] %d-th sequence is generated." % (arrow.now(), b+1), file=sys.stderr)
            b += 1
        # fit the data into a tensor
        data = np.zeros((batch_size, max_len, 3))
        for b in range(batch_size):
            data[b, :points_list[b].shape[0]] = points_list[b]
        return data, sizes


def plot_3d_pointprocess_lam_f(points, lam, plot_ts, T, S=[[0., 1.], [0., 1.]], ngrid=100):
    """
    visualize 3 dimensional point process

    Args:
    - points: [batch_size, 3]
    - plot_ts: scalar
    """
    ss      = [np.linspace(S_k[0], S_k[1], ngrid) for S_k in S]
    ss      = np.array(list(product(*ss)))

    # compute lambda
    evals   = []
    his_p   = points[(points[:, 0] < plot_ts) * (points[:, 0] > 0)]
    his_t   = his_p[:, 0]
    his_s   = his_p[:, 1:]

    for s in ss:
        evals.append(lam.value(plot_ts, his_t, s, his_s))
    evals   = np.array(evals)

    # compute f
    lamvals = []
    last_t  = his_t[-1] if len(his_t) > 0 else 0.
    ts      = np.linspace(last_t, plot_ts, ngrid)
    unit_vol = np.prod([plot_ts - last_t] + [S_k[1] - S_k[0] for S_k in S]) / (ngrid - 1) ** 3

    for t in ts[1:]:
        for s in ss:
            lamval = lam.value(t, his_t, s, his_s)
            lamvals.append(lamval)
    integral = np.sum(lamvals) * unit_vol
    fvals  = evals * np.exp(-integral)
    
    # plot lambda and f
    fig = plt.figure(figsize=(12, 4))

    ax1 = fig.add_subplot(121)
    im  = ax1.imshow(evals.reshape(ngrid, ngrid).T)
    ax1.set_xticks([0, ngrid-1])
    ax1.set_xticklabels([S[0][0], S[0][1]])
    ax1.set_yticks([0, ngrid-1])
    ax1.set_yticklabels([S[1][0], S[1][1]])
    fig.colorbar(im, ax=ax1, shrink=0.8)
    ax1.set_title(r"$\lambda(%.1f, \cdot)$" % plot_ts, fontsize=18)

    ax2 = fig.add_subplot(122)
    im  = ax2.imshow(np.array(fvals).reshape(ngrid, ngrid).T, cmap="magma")
    ax2.set_xticks([0, ngrid-1])
    ax2.set_xticklabels([S[0][0], S[0][1]])
    ax2.set_yticks([0, ngrid-1])
    ax2.set_yticklabels([S[1][0], S[1][1]])
    fig.colorbar(im, ax=ax2, shrink=0.8)
    ax2.set_title(r"$f(%.1f, \cdot)$" % plot_ts, fontsize=18)
    plt.show()


def plot_3d_pointprocess_avg_lam(points, lam, T, S=[[0., 1.], [0., 1.]], ngrid=100):
    """
    visualize 3 dimensional point process

    Args:
    - points: [batch_size, 3]
    - plot_ts: scalar
    """
    ts      = np.linspace(T[0], T[1], ngrid)
    ss      = [np.linspace(S_k[0], S_k[1], ngrid) for S_k in S]
    ss      = np.array(list(product(*ss)))

    def lamval_at_t(t):
        his_p   = points[(points[:, 0] < t) * (points[:, 0] > 0)]
        his_t   = his_p[:, 0]
        his_s   = his_p[:, 1:]
        lams    = [lam.value(plot_ts, his_t, s, his_s) for s in ss]
        return lams

    # compute lambda
    lamvals = [np.mean(lamval_at_t(t)) for t in tqdm(ts)]
    
    # plot lambda and f
    fig = plt.figure(figsize=(6, 4))
    ax1 = fig.add_subplot(111)
    ax1.plot(ts, lamvals)
    ax1.set_xticks([T[0], T[1]])
    ax1.set_xticklabels([T[0], T[1]])
    ax1.set_title(r"Average $\lambda$", fontsize=18)

    zros = np.zeros(points.shape[0])
    ax1.scatter(points[:, 0], zros, c="red", s=10)
    plt.show()