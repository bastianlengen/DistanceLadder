'''
This module contains the functions that correct for different relativistic effects (RLB, K-corrections) by following
the methodology from Anderson (2019, 2022), [2019A&A...631A.165A] and [2022A&A...658A.148A].
'''
import numpy as np
import fit_parameters as fp
from scipy.interpolate import RegularGridInterpolator

def RLB_correction(DF_dict):
    '''
    Correct the DataFrames for the Redshift Leavitt Bias (RLB) on Cepheids by following the methodology from 
    Anderson (2019) [2019A&A...631A.165A].
    
    Parameters
    ----------
    DF_dict : dict of pandas DataFrame
        Dictionary that contains the different pandas DataFrame that have to be corrected before the fit.
    '''
    Cepheids = DF_dict['Cepheids']
    Cepheids_anchors = DF_dict['Cepheids_anchors']

    Cepheids['logP'] = Cepheids['logP'] - np.log10(1+Cepheids['z'])
    Cepheids_anchors['logP'] = Cepheids_anchors['logP'] - np.log10(1 + Cepheids_anchors['z'])
    return

def interpolate_function(table, is_Cep):
    '''
    Create multilinear interpolations of Table A1 from Anderson (2022) [2022A&A...658A.148A]. These interpolations are
    done for the filter I (F814W) for the TRGB and Cepheids, and the filters H (F160W) and V (F555W) for the Cepheids.

    Parameters
    ----------
    table : pandas DataFrame
        Table A1 from Anderson (2022) [2022A&A...658A.148A].
    is_Cep : bool
        True for Cepheids K-corrections, False for TRGB K-corrections.

    Returns
    -------
    interpolate_I : function
        Function that returns the K-corrections in the I band for a set of parameters [Teff, logg, [Fe/H], z, E(B-V)].
    interpolate_H : function
        Function that returns the K-corrections in the H band for a set of parameters [Teff, logg, [Fe/H], z, E(B-V)].
        Note that this returns None for TRGB.
    interpolate_V : function
        Function that returns the K-corrections in the V band for a set of parameters [Teff, logg, [Fe/H], z, E(B-V)].
        Note that this returns None for TRGB.
    '''
    # Get the grid values
    Teff_grid = table['Teff'].drop_duplicates().values
    logg_grid = table['logg'].drop_duplicates().values
    FeH_grid = table['[Fe/H]'].drop_duplicates().values
    z_grid = table['z'].drop_duplicates().values
    EBV_grid = table['E(B-V)'].drop_duplicates().values

    # Create the numpy 5-dimensional array for the data (i.e. f(Teff, logg, FeH, z, EBV))
    I = np.zeros(shape=(len(Teff_grid), len(logg_grid), len(FeH_grid), len(z_grid),len(EBV_grid)))
    if is_Cep == True:
        H, V = I.copy(), I.copy() # Same shape

    # Fill the result 5D array
    for i in table.index:
        # Index
        a = np.where(Teff_grid == table.loc[i, 'Teff'])
        b = np.where(logg_grid == table.loc[i, 'logg'])
        c = np.where(FeH_grid == table.loc[i, '[Fe/H]'])
        d = np.where(z_grid == table.loc[i, 'z'])
        e = np.where(EBV_grid == table.loc[i, 'E(B-V)'])

        # What to interpolate
        I[a, b, c, d, e] = table.loc[i, 'F814WK']
        if is_Cep == True:
            H[a, b, c, d, e] = table.loc[i, 'F160WK']
            V[a, b, c, d, e] = table.loc[i, 'F555WK']

    # Create the interpolation functions
    interpolate_I = RegularGridInterpolator((Teff_grid, logg_grid, FeH_grid, z_grid, EBV_grid), I)
    interpolate_H = None    # None for TRGB
    interpolate_V = None    # None for TRGB
    if is_Cep == True:
        interpolate_H = RegularGridInterpolator((Teff_grid, logg_grid, FeH_grid, z_grid, EBV_grid), H)
        interpolate_V = RegularGridInterpolator((Teff_grid, logg_grid, FeH_grid, z_grid, EBV_grid), V)
    return interpolate_I, interpolate_H, interpolate_V

def interpolated_K_corr_Cep(DF_dict, table, EBV, interpolated_IHV=None):
    '''
    This function will apply the K-corrections on Cepheids by following the methodology and Table A1 from Anderson
    (2022) [2022A&A...658A.148A]. It either uses the interpolation functions for the Table A1 if they already exist,
    or either generates the interpolation functions.
    The parameters [Fe/H], z are taken from the DataFrames. The parameters Teff and logg are computed from the
    eq. (20, 21) from Anderson (2022). However, the color excess E(B-V) has to be decided beforehand, usually in
    fit_parameters.py


    Parameters
    ----------
    DF_dict : dict of pandas DataFrame
        Dictionary that contains the different pandas DataFrame that have to be corrected before the fit.
    table : table : pandas DataFrame
        Table A1 from Anderson (2022) [2022A&A...658A.148A].
    EBV : float
        Value of the color excess E(B-V) that will be considered for the interpolation.
    interpolated_IHV : list of functions
        Contains the list of the interpolation functions for the K-corrections in the I, H, V bands. Note that if the
        value is set to None, it will do the interpolation.

    Returns
    -------
    interpolated_IHV : list of functions
        Contains the list of the interpolation functions for the K-corrections in the I, H, V bands.
    '''
    # Load the functions
    if interpolated_IHV==None:
        interpolated_IHV = interpolate_function(table, is_Cep=True)
    [Kcorr_I, Kcorr_H, Kcorr_V ] = interpolated_IHV

    # Useful functions
    def Kcorr(Teff, logg, FeH, z, EBV):
        total_Kcorr =  Kcorr_H([Teff, logg, FeH, z, EBV]) -\
                       fp.R*(Kcorr_V([Teff, logg, FeH, z, EBV])-Kcorr_I([Teff, logg, FeH, z, EBV]))
        return  total_Kcorr
    def fun_Teff(logP):
        return 10**(-0.0753*logP + 3.8094) # eq. (20) Anderson 2022
    def fun_logg(logP):
        return -0.8808*logP + 2.1909 # eq. (21) Anderson 2022
    def correct_DF(DF):
        for i in DF.index:
            logP = DF.loc[i, 'logP']
            Teff = fun_Teff(logP)
            logg = fun_logg(logP)
            FeH = DF.loc[i, 'M/H']
            z = DF.loc[i, 'z']
            # Make sure Teff in [3500, 6000]
            if Teff>6000:
                print(f'WARNING: Teff {Teff}>6000 -> set to Teff=6000 for the K-corrections at index {i}.')
                Teff = 6000
            elif Teff<3500:
                print(f'WARNING: Teff {Teff}<3500 -> set to Teff=3500 for the K-corrections at index {i}.')
                Teff = 3500
            # Make sure logg in [0,2]
            if logg>2:
                print(f'WARNING: logg {logg}>2 -> set to logg=2 for the K-corrections at index {i}.')
                logg=2
            elif logg<0:
                print(f'WARNING: logg {logg}<0 -> set to logg=0 for the K-corrections at index {i}.')
                logg=0
            # Make sure FeH in [-2, 0.5]
            if FeH>0.5:
                print(f'WARNING: FeH {FeH}>0.5 -> set to FeH=0.5 for the K-corrections at index {i}.')
                FeH = 0.5
            elif FeH<-2:
                print(f'WARNING: FeH {FeH}<-2 -> set to FeH=-2 for the K-corrections at index {i}.')
                FeH = -2
            # Make sure z in [0, 0.03]
            if z>0.03:
                print(f'WARNING: z {z}>0.03 -> set to z=0.03 for the K-corrections at index {i}.')
                z = 0.03
            elif z<0:
                print(f'WARNING: z {z}<0 -> set to z=0.000 for the K-corrections at index {i}.')
                z = 0
            DF.loc[i, 'mW'] = DF.loc[i, 'mW'] - Kcorr(Teff, logg, FeH, z, EBV)
        return

    # Correct each DF
    print('K-correcting the Cepheids DataFrame...')
    correct_DF(DF_dict['Cepheids'])
    print('K-correcting the Cepheids_anchors DataFrame...')
    correct_DF(DF_dict['Cepheids_anchors'])
    if fp.include_MW == True:
        print('K-correcting the Cepheids_MW DataFrame...')
        correct_DF(DF_dict['Cepheids_MW'])
    return interpolated_IHV

def interpolated_K_corr_TRGB(DF_dict, table, Teff, logg, FeH, EBV, interpolated_IHV=None):
    '''
    This function will apply the K-corrections on TRGB by following the methodology and Table A1 from Anderson
    (2022) [2022A&A...658A.148A]. It either uses the interpolation functions for the Table A1 if they already exist,
    or either generates the interpolation functions.
    The parameters z are taken from the DataFrames. However, the color excess Teff, logg, [Fe/H] and E(B-V)
    have to be decided beforehand, usually in fit_parameters.py


    Parameters
    ----------
    DF_dict : dict of pandas DataFrame
        Dictionary that contains the different pandas DataFrame that have to be corrected before the fit.
    table : table : pandas DataFrame
        Table A1 from Anderson (2022) [2022A&A...658A.148A].
    Teff : float
        Value of the effective temperature Teff that will be considered for the interpolation.
    logg : float
        Value of the surface gravity logg that will be considered for the interpolation.
    FeH : float
        Value of the metallicity [Fe/H] that will be considered for the interpolation.
    EBV : float
        Value of the color excess E(B-V) that will be considered for the interpolation.
    interpolated_IHV : list of functions
        Contains the list of the interpolation functions for the K-corrections in the I, H, V bands. Note that if the
        value is set to None, it will do the interpolation. Also, the second and third element are not relevant for TRGB
        and are likely to be None (interpolated_IHV = [fun_I, None, None]).

    Returns
    -------
    interpolated_IHV : list of functions
        Contains the list of the interpolation functions for the K-corrections in the I, H, V bands. Note that since
        the H and V bands are not relevant for TRGB, the second and third element are not relevant for TRGB and are
        None (interpolated_IHV = [fun_I, None, None]).
    '''
    # Load the functions
    if interpolated_IHV is None:
        interpolated_IHV = interpolate_function(table, is_Cep=False)
    Kcorr_I = interpolated_IHV[0]

    # Useful functions
    def correct_DF(DF):
        for i in DF.index:
            z = DF.loc[i, 'z']
            # Make sure z in [0, 0.03]
            if z > 0.03:
                print(f'WARNING: z {z}>0.03 -> set to z=0.03 for the K-corrections at index {i}.')
                z = 0.03
            elif z < 0:
                print(f'WARNING: z {z}<0 -> set to z=0.000 for the K-corrections at index {i}.')
                z = 0
            DF.loc[i, 'm'] = DF.loc[i, 'm'] - Kcorr_I([Teff, logg, FeH, z, EBV]) # Here Kcorr in mmag !!!!
        return

    # Correct each DF
    print('K-correcting the TRGB DataFrame...')
    correct_DF(DF_dict['TRGB'])
    print('K-correcting the TRGB_anchors DataFrame...')
    correct_DF(DF_dict['TRGB_anchors'])
    return interpolated_IHV

### No longer used by the other funcitons, but still available if necessary
def old_K_corr_Cep(DF_dict, filter='W'):
    '''
    Return the corrected the DF_dict for the Cepheids K-corrections following the methodology from Anderson (2021)
    [2022A&A...658A.148A]

    :type   DF_dict: dictionary of pandas DataFrame
    :param  DF_dict: Dictionary that contains the DataFrame that will be fitted.
    :type   filter: string
    :param  filter: filter in which the K-corrections have to be applied, by default the wenseheit W
    '''

    # Defines an interpolate function to interpolate between reference points from Anderson (2021)
    def interpolate(z, z_ref, m_ref, c_ref):
        '''
        Returns the m and c of the linear interpolation between the reference values from Anderson (2022)

        :param z:       redshif of the Cepheid
        :type:          double
        :param z_ref:   Array containing all reference redshift from Anderson (2021)
        :type:          numpy array
        :param m_ref:   Array containing all reference slope m from Anderson (2021)
        :type:          numpy array
        :param c_ref:   Array containing all reference intercept c from Anderson (2021)
        :type:          numpy array
        '''
        # Linear interpolation
        for i in range(len(z_ref) - 1):
            if z_ref[i] <= z and z < z_ref[i + 1]:
                m = m_ref[i] + (z - z_ref[i]) * (m_ref[i + 1] - m_ref[i]) / (z_ref[i + 1] - z_ref[i])
                c = c_ref[i] + (z - z_ref[i]) * (c_ref[i + 1] - c_ref[i]) / (z_ref[i + 1] - z_ref[i])
                return m, c
            else:
                pass
        if z < z_ref[0]:
            m = m_ref[0]
            c = c_ref[0]
        else:
            m = m_ref[-2]
            c = c_ref[-2]

        return m, c

    # Reference points from Anderson (2021)
    z_ref = np.array([0.0019, 0.0056, 0.0098, 0.0172, 0.0245])
    if filter == 'W':
        m_ref = np.array([3.48, 2.68, 1.89, 1.07, 0.31]) * 1e-3
        c_ref = np.array([0.51, 1.74, 3.25, 5.96, 8.05]) * 1e-3
    elif filter == 'F555W':
        m_ref = np.array([-2.84, -8.65, -15.16, -26.85, -38.66]) * 1e-3
        c_ref = np.array([-1.74, -5.47, -9.48, -15.67, -20.51]) * 1e-3
    elif filter == 'F814W':
        m_ref = np.array([-1.02, -3.11, -5.47, -9.40, -12.73]) * 1e-3
        c_ref = np.array([-0.17, -0.91, -1.79, -2.82, -4.02]) * 1e-3
    elif filter == 'F160W':
        m_ref = np.array([-1.18, -3.53, -6.04, -10.10, -14.38]) * 1e-3
        c_ref = np.array([1.00, 1.93, 3.19, 5.69, 8.28]) * 1e-3
    else:
        print('Error, choose a filter in which the Cepheids K-corrections is available !')

    # Load the different DataFrames
    Cepheids = DF_dict['Cepheids']
    Cepheids_anchors = DF_dict['Cepheids_anchors']

    # Correct each DataFrame for it
    for i in Cepheids.index:
        m, c = interpolate(Cepheids.loc[i, 'z'], z_ref, m_ref, c_ref)
        Cepheids.loc[i, 'mW'] = Cepheids.loc[i, 'mW'] \
                              + (m * Cepheids.loc[i, 'logP'] + c) * Cepheids.loc[i,'z'] * Cepheids.loc[i,'V-I'] \
                              - 0.105 * Cepheids.loc[i,'z'] * Cepheids.loc[i,'V-I'] # For F99 redshift law
    for i in Cepheids_anchors.index:
        m, c = interpolate(Cepheids_anchors.loc[i, 'z'], z_ref, m_ref, c_ref)
        Cepheids_anchors.loc[i, 'mW'] = Cepheids_anchors.loc[i, 'mW'] \
                              + (m * Cepheids_anchors.loc[i, 'logP'] + c) * Cepheids_anchors.loc[i,'z'] * Cepheids_anchors.loc[i,'V-I'] \
                              - 0.105 * Cepheids_anchors.loc[i,'z'] * Cepheids_anchors.loc[i,'V-I'] # For F99 redshift law

    if fp.include_MW == True:
        Cepheids_MW = DF_dict['Cepheids_MW']
        for i in Cepheids_MW.index:
            m, c = interpolate(Cepheids_MW.loc[i, 'z'], z_ref, m_ref, c_ref)
            Cepheids_MW.loc[i, 'MW'] = Cepheids_MW.loc[i, 'mW'] \
                              + (m * Cepheids_MW.loc[i, 'logP'] + c) * Cepheids_MW.loc[i,'z'] * Cepheids_MW.loc[i,'V-I'] \
                              - 0.105 * Cepheids_MW.loc[i,'z'] * Cepheids_MW.loc[i,'V-I'] # For F99 redshift law

    return DF_dict

def old_K_corr_TRGB(DF_dict, filter='I'):
    '''
    Return the corrected the DF_dict for the TRGB K-corrections following the methodology from Anderson (2022)
    [2022A&A...658A.148A]

    :type   DF_dict: dictionary of pandas DataFrame
    :param  DF_dict: Dictionary that contains the DataFrame that will be fitted.
    :type   filter: string
    :param  filter: filter in which the K-corrections have to be applied, by default the I-band (F814W)
    '''
    # Parameters from Anderson (2021)
    if filter == 'V':
        a, b = -0.0012, -4.1162
    elif filter == 'I':
        a, b = -0.0004, -1.4075
    elif filter == 'H':
        a, b = 0.0001, -1.6241
    else:
        print('Error, choose a filter in which the Cepheids K-corrections is available !')
        return

    # Load the different DataFrames
    TRGB = DF_dict['TRGB']
    TRGB_anchors = DF_dict['TRGB_anchors']

    # Apply the correction:
    for i in TRGB.index:
        TRGB.loc[i,'m'] = TRGB.loc[i,'m'] \
                        + (a + b * TRGB.loc[i,'z']) * TRGB.loc[i,'z'] * TRGB.loc[i,'V-I']
    for i in TRGB_anchors.index:
        TRGB_anchors.loc[i,'m'] = TRGB_anchors.loc[i,'m'] \
                                + (a + b * TRGB_anchors.loc[i,'z']) * TRGB_anchors.loc[i,'z'] * TRGB_anchors.loc[i,'V-I']
    return DF_dict
