import numpy as np
from numpy.fft import fft2
from numpy.fft import ifft2, ifftshift
import numpy.random
from numpy.random import default_rng
import scipy.constants as sc
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib_scalebar.scalebar import ScaleBar
import random
import sys
from math import radians
import pickle
from matplotlib import patches
import math


# SEED

# seed = 17
# numpy.random.seed(seed)


# QUANTITIES

h = sc.h
m_e = sc.m_e
e = sc.e
c = sc.c
pi = np.pi


def calc_Ronchigram(imdim, simdim,
                    C10_mag, C12_mag, C21_mag, C23_mag, C30_mag, C32_mag, C34_mag, C41_mag, C43_mag, C45_mag, C50_mag, C52_mag, C54_mag, C56_mag,
                    C10_ang, C12_ang, C21_ang, C23_ang, C30_ang, C32_ang, C34_ang, C41_ang, C43_ang, C45_ang, C50_ang, C52_ang, C54_ang, C56_ang,
                    I, b, t, aperture_size, zhiyuanRange=False, seed=None):
    """Takes the aberration coefficient magnitudes mentioned above (in Krivanek notation) and returns a NumPy array of
    the resulting Ronchigram.

    parameters
    imdim: output Ronchigrams have dimensions imdim x imdim px, int
    simdim: maximum alpha (tilt) angle in Ronchigram/rad, num (i.e. maximum angle of inclination of electrons to normal)
    Cnm_mag: magnitude of aberration of order n and rotational symmetry m (in Krivanek notation)/m, num
    # TODO: make sure C10's magnitude is actually in m
    Cnm_ang: angle of aberration of order n and rotational symmetry m (in Krivanek notation)/rad, num
    # PEAK: parameter dictating the amount of Poisson noise applied to the Ronchigram, num
    I: quoted electron current in Ronchigram generation/A, num
    b: fraction of I that reaches the detector, num
    t: Ronchigram aquisition time/s, num
    aperture_size: "Condenser aperture semi-angle (RADIUS)" 
        (https://github.com/noahschnitzer/ronchigram-matlab/blob/master/misc/example.m and also see mention of A(q) in
        https://arxiv.org/abs/2204.11126) in rad
    zhiyuanRange: whether or not I am including Zhiyuan's range for values of noise_fun, i.e. random-uniformly in the 
        range [0, 0.2pi), True of False
    seed: seed passed to add random phases to the beam; this is passable because it would be good to randomly pick a 
        seed in Parallel_HDF5_2.py, save it to HDF5 and pass it to the Ronchigram so that it could be saved along with 
        the Ronchigram for reproducibility

    returns
    Ronchigram, numpy.ndarray
    """

    # n is order of geometrical aberration, m is rotational symmetry
    n_list = (1, 1, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 5)
    m_list = (0, 2, 1, 3, 0, 2, 4, 1, 3, 5, 0, 2, 4, 6)

    # These are the magnitudes of each aberration Cn,m (Cn,m are aberration names in Krivanek notation (Krivanek, Dellby
    # and Lupini, 1999)). The terms below are named in Table 1 of (Kirkland, 2011), which is compiled from (Krivanek,
    # Dellby and Lupini, 1999) and (Krivanek et al., 2008).
    mag_list = (
                # C01_mag,    # C0,1 magnitude/m (image shift)
                C10_mag,    # C1,0 magnitude/m (defocus)
                C12_mag,    # C1,2 magnitude/m (2-fold astigmatism)

                C21_mag,    # C2,1 magnitude/m (axial coma)
                C23_mag,    # C2,3 magnitude/m (3-fold astigmatism)

                C30_mag,    
                C32_mag,
                C34_mag,
                
                C41_mag,
                C43_mag,
                C45_mag,
                
                C50_mag,
                C52_mag,
                C54_mag,
                C56_mag)
    # NOTE: in https://github.com/noahschnitzer/ronchigram-matlab/blob/master/simulation/aberration_generator.m there is 
    # mention of a variable called "ang" being the unit for defocus' magnitude; this stands for Angstrom, not angle.

    # TODO: discern what type of lens (e.g. over or under-focussed) the signs allude to in the later aberration function
    #   equation
    # TODO: check if chromatic aberration should be accounted for

    # Orientation angles phi_n,m for each aberration; follows same convention as np.arctan2
    ang_list = (
                # C01_ang,    # C0,1 angle/rad (image shift)
                C10_ang,    # C1,0 angle/rad
                C12_ang,    # C1,2 angle/rad

                C21_ang,    # C2,1 angle/rad
                C23_ang,    # C2,3 angle/rad

                C30_ang,
                C32_ang,
                C34_ang,
                
                C41_ang,
                C43_ang,
                C45_ang,
                
                C50_ang,
                C52_ang,
                C54_ang,
                C56_ang)

    def chi_term(al, phi, av, n, m, mag, ang):
        """Takes an aberration and determines its contribution to chi (aberration function) for a given convergence angle 
        and azimuthal angle.

        al: convergence angle/rad, num
        phi: azimuthal angle/rad, num
        av: accelerating voltage/V (not relativistically corrected), num
        n: order of aberration, int
        m: degree of aberration, int
        mag: magnitude of aberration/unit, num
        ang: angle of orientation of aberration/rad, num

        returns: numpy.float64
        """

        wavlen = calc_wavlen(av)

        # Term of aberration function equation mentioned in (Schnitzer, Sung and Hovden, 2019), originally from
        #   Krivanek et al., 1999)
        return 2*np.pi/wavlen * mag * al**(n+1) * np.cos(m*(phi-ang)) / (n+1)


    def chi_value(al, phi, av, n_list, m_list, mag_list, ang_list):
        """For a given convergence angle and azimuthal angle, takes aberrations information stored in lists (index
        corresponds to specific aberration) and calculated aberration function value.

        al: convergence angle/rad, num
        phi: azimuthal angle/rad, num
        av: accelerating voltage/V (not relativistically corrected), num
        n: orders of aberration, list
        m: degree of aberration, list
        mag: magnitude of aberration/unit, list
        ang: angle of orientation of aberration/rad, list

        returns: numpy.float64
        """

        chi_terms = [chi_term(al, phi, av, n, m, mag, ang) for n, m, mag, ang in zip(n_list, m_list, mag_list, ang_list)]

        # Aberration function equation mentioned in (Schnitzer, Sung and Hovden, 2019)
        return sum(chi_terms)


    def chi_grid(imdim, al_max, av, n_list, m_list, mag_list, ang_list):
        """Creates an imdim by imdim array of aberration function values for convergence angles (al) with components of magnitudes
        between -al_max and +al_max, for a given set of aberrations; returns an equally sized array containing the
        convergence angle radii at each point, too.

        imdim: length of side of image in pixels (or of array in elements), num
        al_max: magnitude of the maximum magnitude of a convergence angle component/rad, num
        av: accelerating voltage/V (not relativistically corrected), num
        n: orders of aberration, list
        m: degree of aberration, list
        mag: magnitude of aberration/unit, list
        ang: angle of orientation of aberration/rad, list

        returns: tuple(chi_array, al_array)
        chi_array: array of aberration function values, numpy.ndarray
        al_rr: array of converge angle radii/rad, numpy.ndarray
        """
        # The below was written with the assistance of (Schnitzer, 2020c)

        # 1D vector containing convergence angles' possible x- and y- component values. The third argument is
        # imdim because the images in question contain imdim by imdim pixels.
        al_components = np.linspace(-al_max, al_max, imdim)

        # 2d grid of convergence angle vectors formed of different combinations of x- and y- components above.
        al_grid = np.meshgrid(al_components, al_components)

        al_xx, al_yy = al_grid

        al_rr = np.sqrt(al_xx ** 2 + al_yy ** 2)

        # Finding azimuthal angle at each grid point, using arctan2 to account for quadrant position.
        phi = np.arctan2(al_yy, al_xx)

        chi_array = chi_value(al_rr, phi, av, n_list, m_list, mag_list, ang_list)

        return (chi_array, al_rr)


    # CALCULATING THE INTERACTION PARAMETER SIGMA MENTIONED IN (Schnitzer, Sung and Hovden, 2019)

    def calc_wavlen(av):
        """Calculates relativistically corrected electron wavelength given accelerating voltage (Williams and Carter, 2009).
        N.B. requires h/Js, m_e (electron rest mass/kg), e (electron charge/J) and c/ms**-1 to be assigned globally as
        variables.

        av: accelerating voltage/V (not relativistically corrected), num

        returns: wavelength/m, num
        """

        # This has been shown on paper (by me) to be approximately equal to the lambda equation in shifted_ronchigram_m.txt,
        # which I am unsure uses the relativistically corrected electron wavelength.
        wavlen = h / np.sqrt(2 * m_e * e * av * (1 + e * av / (2 * m_e * c ** 2)))

        # print(f"Wavelength is {wavlen*10**12}pm")
        return wavlen


    # SIMULATION PARAMETERS FROM (Schnitzer, 2020b) and (Schnitzer, 2020c)

    imdim = imdim    # Output Ronchigram size/pixels

    simdim = simdim    # Simulation radius in reciprocal space/rad (essentially, the maximum tilt angle)
    # 50-80mrad is a lot more realistic today, according to Chen


    # NOISE CALCULATIONS FROM (Schnitzer, 2020c)

    # From the below code, nnoise seems to be the number of times we add white noise to our noise kernel; nnoise > 1 
    # would mean doing this multiple times, leading to a more white-noisy noise kernel.
    nnoise = 1
    noisefact = 16

    initialNoiseImdim = imdim

    assert initialNoiseImdim % noisefact == 0
    noise_kernel_size = int(initialNoiseImdim/noisefact)    # 256 ->32, 512 ~ 32, 1024 -> 128   # Comment meaning

    assert initialNoiseImdim % noise_kernel_size == 0
    resize_factor = int(initialNoiseImdim/noise_kernel_size)

    noise_fn = np.zeros((noise_kernel_size, noise_kernel_size))

    if zhiyuanRange:

        for i in range(nnoise):
            # Zhiyuan said he used values in the range 0 and 0.2pi for the phase; because nnoise==1, noise_fn /= nnoise 
            # followed by noise_fn += 1 folllowed by noise_fn /= 2 shouldn't actually change the range below [-1, 0.6) 
            # by very much--it should just become [0, 0.8); then, the resizing changes some values a bit but they are 
            # still mostly in the range [0, 0.8); finally, in exp_part, inter_param / inter_param_0 is approximately 1, 
            # meaning the exponent is approximately in the range [0, -0.2pi); previously, Zhiyuan said the negative sign
            # was fine so I will keep it.
            noise_fn += numpy.random.uniform(-1, 0.6, size=(noise_kernel_size, noise_kernel_size))

    else:

        for i in range(nnoise):
            noise_fn += numpy.random.default_rng(seed).standard_normal(size=(noise_kernel_size, noise_kernel_size))

    # print(noise_fn)

    # TODO: figure out where they cut off frequencies above Kmax/2

    # The below is done in order to roughly get noise_fn into a distribution that leads to an expectation value of 1/2 
    # in noise_fun's distribution, then an expectation value of about pi/8 (in between pi/16 and pi/4, which Zhiyuan 
    # Ding (on 16/03/22, over Teams) suggests is reasonable for a carbon thin film) when pi/4 is multiplied by 
    # noise_fun in calculations further below (i.e. in projected potential calculations).
    noise_fn /= nnoise
    noise_fn += 1
    noise_fn /= 2

    new_shape = tuple([resize_factor * i for i in noise_fn.shape])
    noise_fun = np.array(Image.fromarray(noise_fn).resize(size=new_shape))

    # if imdim == 256:

    #     with open('/home/james/VSCode/Simulations/noise_funSeed17imdim256.pkl', 'wb') as f:

    #         pickle.dump(noise_fun, f)

    # else:

    #     f = open('/home/james/VSCode/Simulations/noise_funSeed17imdim256.pkl', 'rb')

    #     print(True)

    #     noise_fun = pickle.load(f)

    #     f.close()

    #     noise_fun = np.resize(noise_fun, (imdim, imdim))


    # CALCULATING THE TRANSMISSION FUNCTION PSI_T(X)

    av = 300 * 10**3    # Acceleration voltage/V (not relativistically corrected)
    kev = av / 1000 # Electron energy/keV (not relativistically corrected)

    # Chi is the aberration function
    chi_array = chi_grid(imdim, simdim, av, n_list, m_list, mag_list, ang_list)[0]
    al_rr = chi_grid(imdim, simdim, av, n_list, m_list, mag_list, ang_list)[1]

 

    # Computing condenser aperture (Schnitzer, 2020c), A(q) in https://arxiv.org/abs/2204.11126

    condenser_ap = al_rr <= aperture_size

    # fig, ax = plt.subplots()
    # ax.axis("off")
    # tmp = np.exp(-1j*chi_array*condenser_ap)
    # ax.imshow(np.angle(tmp), interpolation="nearest")

    # scale = 2*simdim/imdim * 1000    # mrad per pixel
    # scalebar = ScaleBar(scale, units="mrad", dimension="angle")

    # ax.add_artist(scalebar)
    
    # plt.show()

    fft_psi_p = fft2(np.exp(-1j*chi_array) * condenser_ap)    # (Schnitzer, 2020a)
    # fft_psi_p = fft2(np.exp(-1j*chi_array))    # (Schnitzer, 2020a)

    showProbe = False

    if showProbe:

        fig, ax = plt.subplots()
        ax.axis("off")
        ax.imshow(abs(ifftshift(fft_psi_p))**2, interpolation="nearest")

        scale = calc_wavlen(av) / (2 * simdim) # m per pixel
        print(scale)
        scalebar = ScaleBar(scale, units="m", dimension="si-length")

        ax.add_artist(scalebar)
        
        plt.show()

    # print(calc_wavlen(av))

    # Schnitzer's, from (Schnitzer, 2020c)
    inter_param_schnitzer = 2*pi/(calc_wavlen(av)*kev/e*1000)*(m_e*c**2+kev*1000)/(2*m_e*c**2+kev*1000)
    exp_part = np.exp(-1j * np.pi/4 * noise_fun * inter_param_schnitzer / (1.7042*10**-12))   # Schnitzer's

    # Transmission wavefunction under the eikonal approximation (Schnitzer, Sung and Hovden, 2019)
    psi_t = fft_psi_p * exp_part

    # CALCULATING THE RONCHIGRAM

    # inverse = ifft2(psi_t) # (Schnitzer, Sung and Hovden, 2020), (Schnitzer, 2020c)
    inverse = ifft2(psi_t) * condenser_ap # (Schnitzer, Sung and Hovden, 2020), (Schnitzer, 2020c)

    # plt.imshow(np.angle(inverse))
    # plt.show()

    ronch = abs(inverse)**2 # (Schnitzer, Sung and Hovden, 2020)

    # NOTE: it is physically inaccurate for this (particularly the incrementation bit) to come before the Poisson noise 
    # application UNLESS there is a mask applied recently as above, for reasons mentioned in Google Drive on 11/05/22
    ronch -= np.amin(ronch)
    ronch /= np.amax(ronch)

    # For detector Poisson noise, I previously followed https://stackoverflow.com/questions/19289470/adding-poisson-noise-to-an-image 
    # for assistance, except with 255 replaced by 1 because normalisation of ronch somewhere above lead to array elements between 0 and 1. I took
    # yuxiang.li's suggestion, but only their upper one, because the lower one looked like it simply added the Poisson noise
    # to the image, which didn't seem right since Poisson noise isn't additive. 
    # Now, however, I am using my own formulation of Poisson noise derived in the 02/12/2021 entry of my lab book.

    # I is quoted electron current/A (Angus mentioned picoamps being a typical scale)
    # b is fraction of I that reaches the detector
    # t is Ronchigram collection time/s (I overheard Chen and Angus perhaps mention 1s)
    # See 02/12/2021 entry to lab book for derivation of the below
    lam = I * t / sc.e * b * ronch / np.sum(ronch)
    rng = np.random.default_rng(seed)   # Random number generator that NumPy documentation recommends
    ronch = rng.poisson(lam)


    # NORMALISING THE RONCHIGRAM (TO ARRAY VALUES BETWEEN 0 AND 1)

    # (Schnitzer, 2020c)
    # ronch = ronch.astype(np.float32)
    # ronch -= np.amin(ronch)
    # ronch /= np.amax(ronch)

    # print(type(ronch))
    # print(ronch.shape)
    return ronch


if __name__ == "__main__":

    # RONCHIGRAM CALCULATION

    # randu = numpy.random.uniform

    # aberList = [
    # 'O2', 'A2', 'P3', 'A3', 'O4', 'Q4', 'A4', 'P5', 'R5', 'A5', 'O6', 'Q6', 'S6', 'A6', 'P7', 'R7', 'T7', 'A7'
    # ]

    # f = open('/home/james/VSCode/currentPipelines/aberCalcResults_2022_04_29_OPQ.pkl', 'rb')

    # allResultSets = pickle.load(f)

    # mag_units = [10**-9] * 4 + [10**-6] * 6 + [10**-3] * 4

    # # time = '8:41:47'

    # # aberCalcResult = output[time]

    # # mag_list = [eval(aberCalcResult[aber]['mag']) for aber in aberList if aber not in ['P7', 'R7', 'T7', 'A7']]
    # # mag_units = [aberCalcResult[aber]['magUnit'] for aber in aberList]


    # # for i, mag_in_unit in enumerate(mag_list):

    # #     unit = mag_units[i]

    # #     if unit == 'nm': mag_in_m = mag_in_unit * 10**-9
    # #     elif unit == 'um': mag_in_m = mag_in_unit * 10**-6
    # #     elif unit == 'mm': mag_in_m = mag_in_unit * 10**-3

    # #     mag_list[i] = mag_in_m


    # # ang_list = [eval(aberCalcResult[aber]['angle']) for aber in aberList if aber not in ['P7', 'R7', 'T7', 'A7']]

    # # for i, ang_in_deg in enumerate(ang_list):

    # #     ang_in_rad = radians(ang_in_deg)

    # #     ang_list[i] = ang_in_rad

    # max_magList = []

    # for aber in aberList:

    #     if aber == 'P7': break

    #     max_mag_in_unit = 0.0

    #     for singleResultSet in allResultSets.values():
    #         aberMag = eval(singleResultSet[aber]['mag'])

    #         if abs(aberMag) > abs(max_mag_in_unit):
    #             max_mag_in_unit = aberMag

    #     max_magList.append(max_mag_in_unit)

    # print(max_magList)

    # for i, max_mag in enumerate(max_magList):

    #     max_magList[i] = max_mag * mag_units[i]

    # print(max_magList)

    # with open('/home/james/VSCode/currentPipelines/max_magList.pkl', 'wb') as f2:

    #     pickle.dump(max_magList, f2)

    # mag_list = [max_mag/2 for max_mag in max_magList]

    # print('\n')
    # print(mag_list)

    # mList = [0, 2, 1, 3, 0, 2, 4, 1, 3, 5, 0, 2, 4, 6]

    # ang_list = []

    # for m in mList:

    #     if m == 0: ang_list.append(0.0)
    #     else: ang_list.append(2 * np.pi / m * 2/4 * m**3)

    # print(ang_list)

    # f.close()

    # print(max_mags)

    # sys.exit()

    f = open('/home/james/VSCode/currentPipelines/max_magList.pkl', 'rb')
    max_magList = pickle.load(f)
    f.close()

    max_C10, max_C12, max_C21, max_C23, max_C30, max_C32, max_C34, max_C41, max_C43, max_C45, max_C50, max_C52, max_C54, max_C56 = max_magList

    mag_list = [
                # 2.5 * 10**-9,
                max_C10 / 2,   # C1,0 magnitude/m (defocus) (aim for maximum of 100nm according to Chen 04/04/22)
                # 25 * 10**-9,
                max_C12 * 1 / 2,    # C1,2 magnitude/m (2-fold astigmatism) (aim for maximum of 100nm according to Chen 04/04/22)
                max_C21 / 2,   # C2,1 magnitude/m (2nd-order axial coma) (aim for maximum of 300nm according to Chen 04/04/22)
                # 78.5 * 10**-9,
                max_C23 / 2,  # C2,3 magnitude/m (3-fold astigmatism) (aim for maximum of 100nm according to Chen 04/04/22)
                # 47.75 * 10**-9,
                # 0,
                # 0,
                # 0,
   
                max_C30 / 2,  # C3,0 magnitude/m (3rd-order spherical aberration) (aim for range between 1um and 1mm)
                # 5.2 * 10**-6,
                max_C32 / 2,  # C3,2 magnitude/m (3rd-order axial star aberration)
                # 5.2 * 10**-6,
                max_C34 / 2,  # C3,4 magnitude/m (4-fold astigmatism)
                # 2.61 * 10**-6,
                # 0,
                # 0,
                # 0,

                max_C41 / 2,   # C4,1 magnitude/m (4th-order axial coma)
                # 2.637 * 10**-6,
                # 0.05 * 10**-3,
                max_C43 / 2,   # C4,3 magnitude/m (3-lobe aberration)
                # # 0.621 * 10**-6,
                # 0.05 * 10**-3,
                max_C45 / 2,   # C4,5 magnitude/m (5-fold astigmatism)
                # # 0.414 * 10**-6,
                # 0.05 * 10**-3,
                # 0,
                # 0,
                # 0,

                max_C50 / 2,    # C5,0 magnitude/m (5th-order spherical aberration)
                # 0.047 * 10**-3,
                # 5 * 10**-3,
                max_C52 / 2,    # C5,2 magnitude/m (5th-order axial star aberration)
                # # 0.000999 * 10**-3,
                # 5 * 10**-3,
                max_C54 / 2,    # C5,4 magnitude/m (5th-order rosette)
                # # 0.000999 * 10**-3,
                # 5 * 10**-3,
                max_C56 / 2]    # C5,6 magnitude/m (6-fold astigmatism)
                # # 0.004 * 10**-3]
                # 5 * 10**-3]
                # 0,
                # 0,
                # 0,
                # 0]

    ang_list = [
                # 2 * np.pi / 1 * 1/2,
                0,              # C1,0 angle/rad
                2 * np.pi / 2 * 1/2,      # C1,2 angle/rad
                # radians(50.61) * 2 + np.pi / 2,

                2 * np.pi / 1 * 1/2,      # C2,1 angle/rad
                # radians(70.38) * 1 + np.pi / 1,
                2 * np.pi / 3 * 1/2,      # C2,3 angle/rad
                # radians(-25.66) * 3 + np.pi / 3,


                0,              # C3,0 angle/rad
                2 * np.pi / 2 * 1/2,      # C3,2 angle/rad
                # radians(-32.39) * 2 + np.pi / 2,
                2 * np.pi / 4 * 1/2,      # C3,4 angle/rad
                # radians(16.85) * 4 + np.pi / 4,

                2 * np.pi / 1 * 1/2,      # C4,1 angle/rad
                # radians(-86.56) * 1 + np.pi / 1,
                2 * np.pi / 3 * 1/2,      # C4,3 angle/rad
                # radians(36.89) * 3 + np.pi / 3,
                2 * np.pi / 5 * 1/2,     # C4,5 angle/rad
                # radians(-0.20) * 5 + np.pi / 5,

                0,              # C5,0 angle/rad
                2 * np.pi / 2 * 1/2,      # C5,2 angle/rad
                # radians(0.00999) * 2 + np.pi / 2,
                2 * np.pi / 4 * 1/2,      # C5,4 angle/rad
                # radians(0.00999) * 4 + np.pi / 4,
                2 * np.pi / 6 * 1/2]     # C5,6 angle/rad
                # radians(25.03) * 6 + np.pi / 6]

    # print(ang_list[1] / (2 * np.pi / 2))
    # print(mag_list[1] / (2 * 50 * 10**-9))

    imdim = 1024

    useZhiyuanParams = False

    if useZhiyuanParams:

        # Zhiyuan's parameters
        dx = 0.1 * 10**-10  # (pixel size on sample plane/real space sampling) / A

        # Lab book 17/03/22 (pixel size on detector plane/diffraction space sampling) / rad. Matches well to zhiyuan_dkgg
        # my_dk = wavlen / imdim * dx
        zhiyuan_dk = 0.19238281249999997 * 10**-3   # (pixel size on detector plane/diffraction space sampling) / rad

        # Just making sure mine and Zhiyuan's dk are similar; the value Zhiyuan provided me above is probably a 
        # rounded value, so there should be some nonzero discrepancy anyway. I checked and they percentDiff is very small,
        # percentDiff = 100 * (my_dk - zhiyuan_dk) / zhiyuan_dk

        # Lab book 17/03/22
        simdim = imdim * zhiyuan_dk / 2

        print(simdim)

        aperture_size = 90 * 10**-3

        zhiyuanRange = False

    else:

        simdim = 180 * 10**-3

        aperture_size = simdim

    ronch = calc_Ronchigram(imdim, simdim, *mag_list, *ang_list, I=10**-9, b=1, t=1, aperture_size=aperture_size, 
                            zhiyuanRange=False, seed=17)

    # print(ronch[512][512])
    # sum = np.sum(ronch)
    # print(sum)
    # sys.exit()


    # Plotting

    fig, ax = plt.subplots()
    ax.axis("off")

    outerCropLength = np.sqrt(2) * 512
    # outerCropSquare = patches.Rectangle((512 - outerCropLength / 2, 512 - outerCropLength / 2), outerCropLength, outerCropLength, edgecolor='b', facecolor='none')
    # ax.add_patch(outerCropSquare)

    innerCropLength = outerCropLength * 80 / 180
    innerCropSquare = patches.Rectangle((512 - innerCropLength / 2, 512 - innerCropLength / 2), innerCropLength, innerCropLength, edgecolor='b', facecolor='none')
    # ax.add_patch(innerCropSquare)

        # Selecting the 80mrad/180mrad part of the Ronchigram while ensuring the scalebar stuff below works properly

    # halfInnerCropLength = math.floor(innerCropLength / 2)
    # ronch = ronch[512 - halfInnerCropLength: 512 + halfInnerCropLength, 512 - halfInnerCropLength: 512 + halfInnerCropLength]

    ax.imshow(ronch, cmap="gray", interpolation="nearest")

    scale = 2*simdim/imdim * 1000    # mrad per pixel
    scalebar = ScaleBar(scale, units="mrad", dimension="angle")

    ax.add_artist(scalebar)

    plt.show()

    # saveFig = input('Save figure? Enter True or False: ')

    # if saveFig:
    #     fig.figure.savefig('/media/rob/hdd1/james-gj/forReport/_.png')

    sys.exit()

    # p1m = [0 * 10**-9, 0 * 10**-9, 0 * 10**-9, 0 * 10**-9]
    # p1a = [0, 2 * np.pi / 2 * 1/2, 2 * np.pi / 1 * 1/2, 2 * np.pi / 3 * 1/2]

    # p2m = [50 * 10**-9, 50 * 10**-9, 0 * 10**-9, 0 * 10**-9]
    # p2a = [0, 2 * np.pi / 2 * 1/2, 2 * np.pi / 1 * 1/2, 2 * np.pi / 3 * 1/2]

    # p3m = [50 * 10**-9, 50 * 10**-9, 0 * 10**-9, 0 * 10**-9]
    # p3a = [0, 2 * np.pi / 2 * 0, 2 * np.pi / 1 * 1/2, 2 * np.pi / 3 * 1/2]

    # p3_2m = [0, 50 * 10**-9, 0 * 10**-9, 0 * 10**-9]
    # p3_2a = [0, 2 * np.pi / 2 * 0, 2 * np.pi / 1 * 1/2, 2 * np.pi / 3 * 1/2]

    # p4m = [0 * 10**-9, 0 * 10**-9, 800 * 10**-9, 0 * 10**-9]
    # p4a = [0, 2 * np.pi / 2 * 1/2, 2 * np.pi / 1 * 1/2, 2 * np.pi / 3 * 1/2]

    # p5m = [0 * 10**-9, 0 * 10**-9, 800 * 10**-9, 0 * 10**-9]
    # p5a = [0, 2 * np.pi / 2 * 1/2, 2 * np.pi / 1 * 0, 2 * np.pi / 3 * 1/2]


    # p6m = [0 * 10**-9, 0 * 10**-9, 0 * 10**-9, 800 * 10**-9]
    # p6a = [0, 2 * np.pi / 2 * 1/2, 2 * np.pi / 1 * 1/2, 2 * np.pi / 3 * 1/2]

    # p7m = [0 * 10**-9, 0 * 10**-9, 0 * 10**-9, 800 * 10**-9]
    # p7a = [0, 2 * np.pi / 2 * 1/2, 2 * np.pi / 1 * 1/2, 2 * np.pi / 3 * 0]


    # for idx, p in enumerate(zip([p1m, p2m, p3m, p3_2m, p4m, p5m, p6m, p7m], [p1a, p2a, p3a, p3_2a, p4a, p5a, p6a, p7a])):

    #     print(p)

    #     mag_list[0: len(p[0])] = p[0]
    #     ang_list[0: len(p[1])] = p[1]

    #     ronch = calc_Ronchigram(imdim, simdim, *mag_list, *ang_list, I=10**-9, b=1, t=1, aperture_size=aperture_size, 
    #                         zhiyuanRange=False, seed = 17)

    #     fig, ax = plt.subplots()
    #     ax.axis("off")
    #     ax.imshow(ronch, cmap="gray", interpolation="nearest")

    #     scale = 2*simdim/imdim * 1000    # mrad per pixel
    #     scalebar = ScaleBar(scale, units="mrad", dimension="angle")
    #     ax.add_artist(scalebar)

    #     saveFig = False

    #     if saveFig:

    #         if idx > 3:

    #             plt.savefig(f"/media/rob/hdd1/james-gj/forReport/DemonstrateAberrations/With Scalebar/p{idx}")

    #         elif idx == 3:

    #             plt.savefig(f"/media/rob/hdd1/james-gj/forReport/DemonstrateAberrations/With Scalebar/p3_2")

    #         else:

    #             plt.savefig(f"/media/rob/hdd1/james-gj/forReport/DemonstrateAberrations/With Scalebar/p{idx + 1}")

    #     plt.show()


    # REFERENCES

    # Jiang, W. and Chiu, W. (2001) “Web-based Simulation for Contrast Transfer Function and Envelope Functions,”
    # Microscopy and Microanalysis, 7(4). doi:10.1007/S10005-001-0004-4.

    # Kirkland, E.J. (2011) “On the optimum probe in aberration corrected ADF-STEM,” Ultramicroscopy, 111(11).
    # doi:10.1016/j.ultramic.2011.09.002.

    # Krivanek, O.L. et al. (2008) “An electron microscope for the aberration-corrected era,” Ultramicroscopy, 108(3).
    # doi:10.1016/j.ultramic.2007.07.010.

    # Krivanek, O.L., Dellby, N. and Lupini, A.R. (1999) “Towards sub-Å electron beams,” Ultramicroscopy, 78(1–4), pp. 1–11.

    # Schnitzer, N. (2020a) ronchigram-matlab/calculate_probe.m at master · noahschnitzer/ronchigram-matlab. Available at:
    # https://github.com/noahschnitzer/ronchigram-matlab/blob/master/simulation/calculate_probe.m (Accessed: October 21,
    # 2021).

    # Schnitzer, N. (2020b) ronchigram-matlab/example.m at master · noahschnitzer/ronchigram-matlab. Available at:
    # https://github.com/noahschnitzer/ronchigram-matlab/blob/master/misc/example.m (Accessed: October 21, 2021).

    # Schnitzer, N. (2020c) ronchigram-matlab/shifted_ronchigram.m at master · noahschnitzer/ronchigram-matlab. Available
    # at: https://github.com/noahschnitzer/ronchigram-matlab/blob/master/simulation/shifted_ronchigram.m (Accessed: October
    # 21, 2021).

    # Schnitzer, N., Sung, S.H. and Hovden, R. (2019) “Introduction to the Ronchigram and its Calculation with
    # Ronchigram.com,” Microscopy Today, 27(3), pp. 12–15. doi:10.1017/S1551929519000427.

    # Schnitzer, N., Sung, S.H. and Hovden, R. (2020) “Optimal STEM Convergence Angle Selection Using a Convolutional
    # Neural Network and the Strehl Ratio,” Microscopy and Microanalysis, 26(5). doi:10.1017/S1431927620001841.

    # Williams, D.B. and Carter, C.B. (2009) Transmission electron microscopy: a textbook for materials science. 2nd
    # edn. New York: Springer.