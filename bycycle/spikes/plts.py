"""Spike plotting functions."""

import numpy as np
import matplotlib.pyplot as plt
from scipy import stats as st

from neurodsp.plts import plot_time_series, plot_bursts
from neurodsp.plts.utils import check_ax

from bycycle.utils.dataframes import get_extrema_df
from bycycle.utils.timeseries import limit_signal
from bycycle.spikes.utils import split_signal
from neurodsp.sim.cycles import sim_skewed_gaussian_cycle

###################################################################################################
###################################################################################################

def plot_spikes(df_features, sig, fs, spikes=None, index=None, xlim=None, ax=None):
    """Plot a group of spikes or the cyclepoints for an individual spike.

    Parameters
    ----------
    df_features : pandas.DataFrame
        Dataframe containing shape and burst features for each spike.
    sig : 1d or 2d array
        Voltage timeseries. May be 2d if spikes are split.
    fs : float
        Sampling rate, in Hz.
    spikes : 1d array, optional, default: None
        Spikes that have been split into a 2d array. Ignored if ``index`` is passed.
    index : int, optional, default: None
        The index in ``df_features`` to plot. If None, plot all spikes.
    xlim : tuple
        Upper and lower time limits. Ignored if spikes or index is passed.
    ax : matplotlib.Axes, optional, default: None
        Figure axes upon which to plot.
    """

    ax = check_ax(ax, (10, 4))

    center_e, _ = get_extrema_df(df_features)

    # Plot a single spike
    if index is not None:

        times = np.arange(0, len(sig)/fs, 1/fs)

        # Get where spike starts/ends
        start = df_features.iloc[index]['sample_start'].astype(int)
        end = df_features.iloc[index]['sample_end'].astype(int)

        sig_lim = sig[start:end+1]
        times_lim = times[start:end+1]

        # Plot the spike waveform
        plot_time_series(times_lim, sig_lim, ax=ax)

        # Plot cyclespoints
        labels, keys = _infer_labels(center_e)
        colors = ['C0', 'C1', 'C2', 'C3']

        for idx, key in enumerate(keys):

            sample = df_features.iloc[index][key].astype('int')

            plot_time_series(np.array([times[sample]]), np.array([sig[sample]]),
                             colors=colors[idx], labels=labels[idx], ls='', marker='o', ax=ax)

    # Plot as stack of spikes
    elif index is None and spikes is not None:

        times = np.arange(0, len(spikes[0])/fs, 1/fs)

        plot_time_series(times, spikes, ax=ax)

    # Plot as continuous timeseries
    elif index is None and spikes is None:

        ax = check_ax(ax, (15, 3))

        times = np.arange(0, len(sig)/fs, 1/fs)

        plot_time_series(times, sig, ax=ax, xlim=xlim)

        if xlim is None:
            sig_lim = sig
            df_lim = df_features
            times_lim = times
            starts = df_lim['sample_start']
        else:
            cyc_idxs = (df_features['sample_start'].values >= xlim[0] * fs) & \
                    (df_features['sample_end'].values <= xlim[1] * fs)

            df_lim = df_features.iloc[cyc_idxs].copy()

            sig_lim, times_lim = limit_signal(times, sig, start=xlim[0], stop=xlim[1])

            starts = df_lim['sample_start'] - int(fs * xlim[0])

        ends = starts + df_lim['period'].values

        is_spike = np.zeros(len(sig_lim), dtype='bool')

        for start, end in zip(starts, ends):
            is_spike[start:end] = True

        plot_bursts(times_lim, sig_lim, is_spike, ax=ax)


def _infer_labels(center_e):
    """Create labels based on center extrema."""

    # Infer labels
    if center_e == 'trough':
        labels = ['Trough', 'Peak', 'Inflection']
        keys = ['sample_trough', 'sample_next_peak', 'sample_end']
    elif center_e == 'peak':
        labels = ['Peak', 'Trough', 'Inflection']
        keys = ['sample_peak', 'sample_next_trough', 'sample_end']

    return labels, keys

def plot_gaussian_fit(df_features, sig, fs, z_thresh_cond, z_thresh_k):

    # Get where spike starts/ends
    start = df_features['sample_start'].astype(int)
    end = df_features['sample_end'].astype(int)

    # Calculate signal parameters
    sig_cyc = sig[start:end+1]
    cyc_len = len(sig_cyc)
    times_cyc = np.arange(0, cyc_len/fs, 1/fs)

    # Get calculated gaussian paramters
    na_params = [cyc_len/fs, fs, df_features['Na_center'], df_features['Na_std'],
                 df_features['Na_alpha'], df_features['Na_height']]

    na_gaus = sim_skewed_gaussian_cycle(*na_params)
    # Plot Na gaussian fit
    plot_sing_gaus(na_gaus, sig_cyc, current_type="Na")

    na_center = int(df_features['Na_center']*cyc_len)
    # Get remaining signal for plotting
    rem_sig = sig_cyc - na_gaus
    rem_sig_k = rem_sig[na_center :,]
    rem_sig_cond = rem_sig[:na_center ,]
    times_k = times_cyc[na_center :,]
    times_cond = times_cyc[:na_center ,]

    # Plot remaining signal
    plt.plot(fs*times_k,rem_sig_k, label="K current region", color="b")
    plt.plot(fs*times_cond,rem_sig_cond, label="Conductive current region", color="green")
    plt.axvline(na_center, color='k')
    plt.title("Remaining signal after subtracting Na current gaussian fit")
    plt.legend()
    plt.ylabel("Voltage (uV)")
    plt.show()

    # Calculate z scores
    z_score_k = st.zscore(rem_sig_k)
    z_score_cond = st.zscore(rem_sig_cond)

    plt.plot(fs*times_k,z_score_k, label="K current region z-score", color="b")
    plt.plot(fs*times_cond,z_score_cond, label="Conductive current region z-score", color="green")
    plt.plot(fs*times_k, np.array([z_thresh_k for i in range(len(times_k))]), 'k--')
    plt.axvline(na_center, color='k')
    plt.plot(fs*times_cond, np.array([z_thresh_cond for i in range(len(times_cond))]), 'k--')
    plt.title("Remaining signal z-scores")
    plt.ylabel("Z-score")
    plt.legend()
    plt.show()

    cond_params = [len(rem_sig_cond)/fs, fs, df_features['Cond_center'],
                   df_features['Cond_std'], df_features['Cond_alpha'], df_features['Cond_height']]
    k_params = [len(rem_sig_k)/fs, fs, df_features['K_center'],
                df_features['K_std'], df_features['K_alpha'], df_features['K_height'] ]

    # Get current gaussians based on fit parameters
    cond_gaus = sim_skewed_gaussian_cycle(*cond_params)
    k_gaus = sim_skewed_gaussian_cycle(*k_params)

    # Plot conductive and potassium current fits
    plot_sing_gaus(cond_gaus, rem_sig_cond, current_type="Conductive")
    plot_sing_gaus(k_gaus, rem_sig_k, current_type="K")

    # Plot all gaussian fits
    plt.plot(sig_cyc, label= "cycle signal", color="k")
    plt.plot(na_gaus)
    plt.plot(fs*times_k, k_gaus)
    plt.plot(fs*times_cond, cond_gaus)
    plt.ylabel("Voltage (uV)")
    plt.title("All gaussian fits found")
    plt.show()


def plot_sing_gaus(gaus, sig, current_type="Na"):
    plt.plot(gaus, label= "skewed gaussian fit", color="red")
    plt.plot(sig, label= "cycle signal", color="k")
    plt.title(current_type + " current gaussian fit")
    plt.ylabel("Voltage (uV)")
    plt.legend()
    plt.show()

def plot_gen_spikes(fs, spikes_gen, index, xlim, ax):

    #plot single spike
    if index is not None:
        times = range(1,1+ len(spikes_gen[index]))
        plot_times = [x/fs for x in times]
        plt.plot(plot_times, spikes_gen[index])
        plt.ylabel("Voltage (uV)")

    else:
        #plot all spikes 
        #get Na current trough for first generated spike 
        align_point = np.argmin(spikes_gen[0])/fs

        for i in range(len(spikes_gen)):
            #get trough of Na current for each spike
            trough = np.argmin(spikes_gen[i])/fs
            #calculate shift between the trough and the align point
            shift = trough - align_point
           
            times = range(1,1+ len(spikes_gen[i]))
            #get aligned time array
            align_times = [(x/fs)-shift for x in times]

            plt.plot(align_times, spikes_gen[i])
            plt.ylabel("Voltage (uV)")
