import h5py
from mpi4py import MPI
import pandas as pd
import numpy as np

# Creating this file to conveniently group together each experimental Ronchigram with properties like aberration 
# constants, acquisition times, noise levels etc, so that inference (particularly predicting c1,2 and phi1,2) can be 
# done on these easily and predicted Ronchigrams can be plotted alongside test Ronchigrams.

# The experimental Ronchigrams I have so far are those that Chen acquired on 29/04/2022, which can be found as: 
# 
# -> .dm3 files in /media/rob/hdd1/james-gj/forReport/2022-04-29/2022-04-29
# 
# -> Since conversion using ImageJ, .png files in /media/rob/hdd1/james-gj/forReport/2022-04-29/PNG Files

# The parent directory of both of the above (/media/rob/hdd1/james-gj/forReport/2022-04-29) contains:
# 
# -> /media/rob/hdd1/james-gj/forReport/2022-04-29/20220429_Ronchigram.xlsx, which has information about the dosage for 
#    acquiring each Ronchigram etc.
# 
# -> /media/rob/hdd1/james-gj/forReport/2022-04-29/cosmo.txt, which has aberration values etc.

# Since processing in txtRead.py, aberCalcResults_2022_04_29_OPQ.pkl currently have all of the aberration information from comso.txt in 
# the following format:
# 
# -> d1 = {aberrationCalculationTime: aberrationCalculationResult}
# 
# -> aberrationCalculationTime = {aberrationType: aberrationParameters}, were aberrationType is either O2 (C1,0), A2 (C1,2), P3 (C2,1) etc.
# 
# -> aberrationParameters = {
#                           'mag': aberration magnitude in magUnit,
#                           'magUnit': unit in which 'mag' is found,
#                           'magError': value that is, ACCORDING TO ZIYI, error associated with mag BUT I MUST DISCOVER ITS UNIT,
#                           'angle': aberration angle (presumably in OPQ form) in angleUnit,
#                           'angleUnit': unit in which 'angle' is found,
#                           'angleError': value that is, ACCORDING TO ZIYI, error associated with angle BUT I MUST DISCOVER ITS UNIT,
#                           'pi/4Limit': I NEED TO ASK CHEN ABOUT THIS but it is a value in pi/4LimitUnit,
#                           'pi/4LimitUnit: unit in which 'pi/4Limit' limit is found
# }

# I want to save the experimental Ronchigrams, along with their aberration constants, in HDF5 format as I have done with  
# the simulations I have used so far--this will make it easy to integrate these with the inference pipelines I already 
# have, particularly comparisonInferencer.py but I could probably also make trend graphs out of these, just the 
# c1,2 and phi1,2 labels wouldn't vary between Ronchigrams in an exactly linear fashion.

# Since I am not exactly sure yet (I am waiting for Chen to tell me) which aberration constants are for which image 
# besides the aberration constants whose recording times are listed in 
# /media/rob/hdd1/james-gj/forReport/2022-04-29/20220429_Ronchigram.xlsx, for now I will just save to HDF5, along with 
# their parameters like aberration constants, noise, capture time etc., the experimental Ronchigrams that are explicitly 
# mentioned in the aforementioned file


# 0: Read the .xlsx file containing the image acquisition parameters

acquisitionParams = pd.read_excel(
    io='/media/rob/hdd1/james-gj/forReport/2022-04-29/20220429_Ronchigram.xlsx', 
    header=0,
    usecols="C:E, G, H",
    skiprows=[4, 6, 9, 12],
    dtype=np.str
    )
print(acquisitionParams)

acquisitionParamsDict = acquisitionParams.to_dict()
print(acquisitionParamsDict)

# Just a dictionary of idx: Image (number), which will be used later when choosing the image to save to a certain idx of the HDF5 file
idxImageNumberDict = acquisitionParamsDict['Image']

# Just a dictionary of idx: Time, which will be used later when saving aberration constant sets to the right location in the HDF5 file
idxTimeDict = acquisitionParamsDict['Time']


# 1. Create the HDF5 datasets as in Parallel_HDF5_2.py; keep the number of processes sort of thing, although this will 
# probably just be given a value of 1
# -> Implement a way to save dose/% (if you haven't yet found out how to convert to current); Cosmo t (s); each aberration 
#    magnitude' error (identified by Ziyi), although Chen hasn't yet verified this or told me its unit; each aberration angle's 
#    error (identified by Ziyi), although Chen hasn't yet verified this or told me its unit; pi/4 limit in METRES for 
#    each aberration

with h5py.File(f'/media/rob/hdd1/james-gj/forReport/2022-04-29/experimentalRonchigrams.h5', 'w', driver='mpio', comm=MPI.COMM_WORLD) as f:

    number_processes = 1
    simulations_per_process = len(acquisitionParamsDict['Image'])

    try:
        # dtype is float64 rather than float32 to reduce the memory taken up in storage.
        random_mags_dset = f.create_dataset("random_mags dataset", (number_processes, simulations_per_process, 14), dtype="float32")
        random_angs_dset = f.create_dataset("random_angs dataset", (number_processes, simulations_per_process, 14), dtype="float32")
        random_I_dset = f.create_dataset("random_I dataset", (number_processes, simulations_per_process, 1), dtype="float32")
        random_t_dset = f.create_dataset("random_t dataset", (number_processes, simulations_per_process, 1), dtype="float32")
        random_seed_dset = f.create_dataset("random_seed dataset", (number_processes, simulations_per_process, 1), dtype="int")
        ronch_dset = f.create_dataset("ronch dataset", (number_processes, simulations_per_process, 1024, 1024), dtype="float32")

        dose_pct_dset = f.create_dataset("dose_pct dataset", (number_processes, simulations_per_process, 1), dtype="float32")
        comso_t_s_dset = f.create_dataset("cosmo_t_s dataset", (number_processes, simulations_per_process, 1), dtype="float32")
        magnitude_error_unknownUnit_dset = f.create_dataset("magnitude_error_unknownUnit dataset", (number_processes, simulations_per_process, 14), dtype="float32")
        angle_error_unknownUnit_dset = f.create_dataset("angle_error_unknownUnit dataset", (number_processes, simulations_per_process, 14), dtype="float32")
        pi_over_4_limit_in_m_dset = f.create_dataset("pi_over_4_limit_in_m dataset", (number_processes, simulations_per_process, 14), dtype="float32")

    except:
        random_mags_dset = f["random_mags dataset"]
        random_angs_dset = f["random_angs dataset"]
        random_I_dset = f["random_I dataset"]
        random_t_dset = f["random_t dataset"]
        random_seed_dset = f["random_seed dataset"]
        ronch_dset = f["ronch dataset"]

        dose_pct_dset = f['dose_pct dataset']
        comso_t_s_dset = f['comso_t_s dataset']
        magnitude_error_unknownUnit_dset = f['magnitude_error_unknownUnit dataset']
        angle_error_unknownUnit_dset = f['angle_error_unknownUnit dataset']
        pi_over_4_limit_in_m_dset = f['pi_over_4_limit_in_m dataset']


    # Probably going to have a for loop for each time a file is being read--don't really want to open a file over and over 
    # again


    # 2. Reading the images and saving them to ronch_dset
    # -> Use /media/rob/hdd1/james-gj/forReport/2022-04-29/20220429_Ronchigram.xlsx to get the numbers of the Ronchigram 
    #    images to save, as well as the times for each image
    # -> Create a dictionary of imageIdx:time for each image, so the correct aberration constants can be collected later for saving 
    #    alongside them; here, imageIdx = image number - 1


    # 3. Make sure the normalization of the above is adequate


    # 4. Save dose/% alongside the above Ronchigrams

    idxDosePctDict = acquisitionParamsDict['Dose(%)']

    for idx, dosePct in idxDosePctDict.items():
        
        dosePct = np.array([eval(dosePct)])

        dose_pct_dset[0, idx] = dosePct


    # 5. Converting dose/% to current/A and save alongside the above Ronchigrams


    # 6. Saving cosmo t (s), which I still don't really know how to descirbe yet, alongside each Ronchigram

    idxCosmo_t_sDict = acquisitionParamsDict['Cosmo t (s)']

    for idx, cosmo_t_s in idxCosmo_t_sDict.items():

        cosmo_t_s = np.array([eval(cosmo_t_s)])

        comso_t_s_dset[0, idx] = cosmo_t_s


    # 7. Saving Orius t (s), which I believe is Ronchigram capture time/s needed for Poisson noise recreation, alongside 
    # each Ronchigram


    # 8. For each time in the list from step 1, remembering to save these constants to position imageIdx in the HDF5 dataset, 
    # get the aberration parameters recorded at this time:
    # -> Aberration magnitude/m
    # -> Aberration angle/degree (will have to convert to radians then multiply by whatever needs multiplying by to get the 
    #    Krivanek notation aberration angle value)
    # -> Aberration magnitude error/unknown unit
    # -> Aberration angle error/unknown unit
    # -> pi/4 limit in metres
    # -> Later, will have to add a way to a