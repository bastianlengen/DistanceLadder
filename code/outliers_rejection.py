'''
This module contains the outlier rejections process that will be called by the different scripts.
'''
import os
import numpy as np
import pandas as pd
import fit_parameters as fp
from fitting import fit_distance_ladder


def single_kappa_clipping(DF_dict, SNe_other, kappa=2.7, work_dir='./', **kwargs):
    '''
    This function performs an outlier rejection following the single-kappa clipping algorithm. It splits the initial
    DataFrame into two different DataFrames. One of them will be fitted, while the other contains the outliers that will
    not be fitted. Note that this function only reject points form the Cepheids, Cepheids_anchors, Cepheids_MW
    or SNe Hubble DataFrames.

    Parameters
    ----------
    DF_dict : dict of pandas DataFrame
        Dictionary that contains the different pandas DataFrame that have to be fitted.
    SNe_other : pandas DataFrame
        DataFrame that contains the SNe that are outside the fitting range [z_min, z_max] for the Hubble diagram.
    kappa : float
        The kappa parameter for which the rejection process stops. By default kappa is 2.7.
    work_dir : string
        Working directory, by default ./

    Returns
    -------
    DF_dict : dict of pandas DataFrame
        Dictionary containing the different pandas DataFrame that will be fitted.
    DF_dict_outlier : dict of pandas DataFrame
        Dictionary containing the different pandas DataFrame that will not be fitted.
    '''
    ### Use of kwargs for the multiple_run.py
    break_P2 = kwargs.get('break_P2', fp.break_P2)


    ### Create the DF_dict_outliers for the outliers and load the DF_dict
    DF_dict_outliers = dict()
    if fp.include_Cepheids == True:
        DF_dict_outliers['Cepheids'] = pd.DataFrame(columns=DF_dict['Cepheids'].columns)
        DF_dict_outliers['Cepheids_anchors'] = pd.DataFrame(columns=DF_dict['Cepheids_anchors'].columns)
        if fp.include_MW == True:
            DF_dict_outliers['Cepheids_MW'] = pd.DataFrame(columns=DF_dict['Cepheids_MW'].columns)
    if fp.fit_aB == True:
        DF_dict_outliers['SNe_Hubble'] = SNe_other

    ### First iteration
    y, q_dict, L = fit_distance_ladder(DF_dict, break_P2=break_P2)[:3]
    q = np.array([]) # Load the q values
    for str in q_dict:
        if str not in ['H0', 'chi2/dof']:
            q = np.append(q, q_dict[str][0])

    ### Initialize the algorithm
    errors = np.array(y - np.matmul(L, q))
    std = np.std(errors)
    #errors = np.abs(errors)
    worst_Cep, worst_SNe = 0, 0 # Set to 0 if there is not both of them for the later comparison
    N_MW, N_Cep, N_anc = 0, 0, 0 # Set to 0 if there is not both of them
    if fp.include_Cepheids == True:
        N_Cep = len(DF_dict['Cepheids'])
        N_anc = len(DF_dict['Cepheids_anchors'])
        if fp.include_MW == True:
            N_MW = len(DF_dict['Cepheids_MW'])*(fp.include_MW==True)
        worst_Cep = np.max(errors[:N_Cep+N_anc+N_MW])
    if fp.fit_aB == True:
        N_SN = len(DF_dict['SNe_Hubble'])
        worst_SNe = np.max(errors[-N_SN:])
    # Compare them
    worst = np.max([worst_SNe, worst_Cep])

    ### Start iterations
    while worst >= fp.kappa*std:
        index_worst = list(errors).index(worst)
        # Get the outlier in the DF_dict_outliers and delete it from the DF_dict
        if fp.include_Cepheids == True:
            if index_worst<N_Cep:
                index = index_worst
                DF_dict_outliers['Cepheids'] = pd.concat ([DF_dict_outliers['Cepheids'],
                                                           DF_dict['Cepheids'].iloc[[index]]])
                DF_dict['Cepheids'] = DF_dict['Cepheids']\
                                    .drop(index=index).reset_index(drop=True)
            elif index_worst<N_Cep+N_anc:
                index = index_worst-N_Cep
                DF_dict_outliers['Cepheids_anchors'] = pd.concat([DF_dict_outliers['Cepheids_anchors'],
                                                                 DF_dict['Cepheids_anchors'].iloc[[index]]])
                DF_dict['Cepheids_anchors'] = DF_dict['Cepheids_anchors']\
                                            .drop(index=index).reset_index(drop=True)
            elif ((fp.include_MW == True) and (index_worst<N_Cep+N_anc+N_MW)):
                index = index_worst-N_Cep-N_anc
                DF_dict_outliers['Cepheids_MW'] = pd.concat([DF_dict_outliers['Cepheids_MW'],
                                                             DF_dict['Cepheids_MW'].iloc[[index]]])
                DF_dict['Cepheids_MW'] = DF_dict['Cepheids_MW']\
                                        .drop(index=index).reset_index(drop=True)
        if ((fp.fit_aB == True) and (index_worst>len(y)-N_SN)):
            offset = len(y)-N_SN
            index = index_worst - offset
            DF_dict_outliers['SNe_Hubble'] = pd.concat([DF_dict_outliers['SNe_Hubble'],
                                                        DF_dict['SNe_Hubble'].iloc[[index]]])
            DF_dict['SNe_Hubble'] = DF_dict['SNe_Hubble']\
                                    .drop(index=index).reset_index(drop=True)

        # Re-iterate
        y, q_dict, L  = fit_distance_ladder(DF_dict, break_P2=break_P2)[:3]
        q = np.array([])  # Load the q values
        for str in q_dict:
            if str not in ['H0', 'chi2/dof']:
                q = np.append(q, q_dict[str][0])

        errors = np.array(y - np.matmul(L, q))
        std = np.std(errors)
        errors = np.abs(errors)
        worst_Cep, worst_SNe = 0, 0  # Set to 0 if there is not both of them for the later comparison
        if fp.include_Cepheids == True:
            N_Cep = len(DF_dict['Cepheids'])
            N_anc = len(DF_dict['Cepheids_anchors'])
            N_MW = 0
            if fp.include_MW == True:
                N_MW = len(DF_dict['Cepheids_MW']) * (fp.include_MW == True)
            worst_Cep = np.max(errors[:N_Cep + N_anc + N_MW])
        if fp.fit_aB == True:
            N_SN = len(DF_dict['SNe_Hubble'])
            worst_SNe = np.max(errors[-N_SN:])
        # Compare them
        worst = np.max([worst_SNe, worst_Cep])

    ### Save the outliers
    out_dir = work_dir + 'outliers/'
    if not os.path.exists(out_dir):
        print(f'I will create the {out_dir} directory for you !')
        os.mkdir(out_dir)
    if fp.include_Cepheids == True:
        N = len(DF_dict_outliers['Cepheids'])
        print(f'A total of {N} Cepheids have been excluded from the Cepheids DataFrame.')
        DF_dict_outliers['Cepheids'].to_csv(out_dir + 'Cepheids.csv', index=False)
        N = len(DF_dict_outliers['Cepheids_anchors'])
        print(f'A total of {N} Cepheids have been excluded from the Cepheids_anchor DataFrame.')
        DF_dict_outliers['Cepheids_anchors'].to_csv(out_dir + 'Cepheids_anchors.csv', index=False)
        if fp.include_MW == True:
            N = len(DF_dict_outliers['Cepheids_MW'])
            print(f'A total of {N} Cepheids have been excluded from the Cepheids_MW DataFrame.')
            DF_dict_outliers['Cepheids_MW'].to_csv(out_dir + 'Cepheids_MW.csv', index=False)
    if fp.fit_aB == True:
        N = len(DF_dict_outliers['SNe_Hubble'])-len(SNe_other)
        print(f'A total of {N} supernovae have been excluded from the SNe_Hubble DataFrame.')
        DF_dict_outliers['SNe_Hubble'].to_csv(out_dir + 'SNe_Hubble.csv', index=False)

    return DF_dict, DF_dict_outliers
