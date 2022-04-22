
from http.client import NO_CONTENT
from multiprocessing.dummy import active_children
import numpy as np
import pandas as pd
import seaborn as sns
import plotly.express as px
import matplotlib.pyplot as plt
from os.path import exists
from pyarrow import csv
from sklearn import preprocessing
from sklearn.preprocessing import MinMaxScaler, normalize,LabelEncoder, RobustScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score 
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.cluster import KMeans
from sklearn.feature_selection import VarianceThreshold
from sklearn import mixture as mx
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.datasets import make_blobs
from scipy.stats.stats import pearsonr
from numpy.random import randint
from sympy import denom, numer
from statsmodels.distributions.empirical_distribution import ECDF
# Classes
#--------------------------------------------------------------------------------------------------------#
class VarianceFilter(BaseEstimator, TransformerMixin):
    def __init__(self, thrshld):
        self.thrshld = thrshld

    def fit(self, X, y = None):
        return self

    def transform(self, X, y=None):
        X_copy = X.copy()
        X_norm = RobustScaler().fit_transform(X.copy())
        X_var = X_norm.var(axis=0)
        X_ = X_copy[:,(X_var < self.thrshld)]
        _,m = np.shape(X_)
        print(f"VF returns features of dim {m}")
        return X_
    
class CorrelationFilter(BaseEstimator, TransformerMixin):
    def __init__(self, thrshld):
        self.thrshld = thrshld

    def fit(self, X, y = None):
        return self

    def transform(self, X, y=None):
        X_ = X.copy()
        i = 0
        _,m = np.shape(X_)
        while i<m: 
            _, m = np.shape(X_)
            corr = np.zeros(shape = m, dtype = bool)
            # Find correlation with all columns j>i
            for j in range(i+1,m):
                c, _ = pearsonr(X_[:,i],X_[:,j])
                corr[j] = np.abs(c) > self.thrshld

            X_ = np.delete(X_, corr, axis = 1)
            if np.mod(m-i,50)== 0:
                print(i,m)
            i += 1
        return X_


def main():
    ## Load data ##
    label_df, feature_df = load_SEQ_data();

    ## Question 1 ##
    q1_plot = {
            "hist_plot":    False,
            "scree_plot":   False,
            "metrics_plot": False, 
            "pair_plot":    False
            }
   # question_1(X_,preprocessor, true_labels, q1_plot)
   
    ## Question 2 ##
    n_inits = 25
    q2_clusters = range(2,8)
    models = [KMeans(n_init = n_inits, init = 'k-means++', n_clusters=i) for i in q2_clusters]
    PACs = question_2(feature_df, models)
    print(PACs)
    plt.show()

def question_1(X_, feature_df, label_df, plot):
    ## Models ## 
    label_encoder = LabelEncoder()
    true_labels = label_encoder.fit_transform(label_df)
    preprocessor = pre_processing()
    n_inits = 5
    clusters = list(range(2,8))
    models = [KMeans(n_init = n_inits, init = 'k-means++', n_clusters=i) for i in clusters]
    gmodels = [mx.GaussianMixture(n_components = i,covariance_type="full", n_init = n_inits) for i in clusters]
    models.extend(gmodels)
    clusters.extend(clusters)
    ## Feature pre - visualisation ##
    if plot["hist_plot"]:
        col_hist(feature_df,1000)
    ## Initial vizualisation ## 
    pca = preprocessor["PCA"]
    if plot["scree_plot"]:
        scree_plot(pca,0.75)
    if plot["pair_plot"]:
        pair_plot(pca, 5)

    ## Run clustering ##
    metrics_df, predicted_labels = run_clustering(X_,models, clusters)
    if plot["metrics_plot"]:
        metrics_plot(metrics_df)

    ## Our clustering:
    model = models[3]
    pred_labels = predicted_labels[model]
    if plot["pair_plot"]:
        pair_plot(X_, 5, pred_labels)
        pair_plot(X_, 5, true_labels)
    ## "Best" metrics + visualize ##
    #pair_plot(X_, 5, true_labels)

    plt.show()
def question_2(feature_df, 
                    models, 
                    k = 100, 
                    p = 0.8, 
                    Q = (0.01, 0.99), 
                    verbose = False):
    """
    inputs:
           X     - numpy array of dim = (samples, no.pca.comps)
           model - initialized sklearn model
           k     - number of subsamples
           p     - proportion of samples 
           Q     - tuple of ecdf thresholds
    output:      - PAC_k value for specificed Q

    TO DO: run several models, plot ecdf and return PAC for all of them (reuse plot_metrics), be able to run with different prepr. settings

    """
    print("Testing stability")
    def update_numerator(numerator, labels, subsample_indices):
        """
        inputs:
               numerator   - matrix dim n*n; sum of connectivity matrices
               pred_labels - vector of dim ~0.8n of labels, remember that this is a subsample¨
               connect     - connectivity matrix for current subsample run

        output:            - added 1 to all (i,j) where labels(i) = labels(j)
            
        """    
        connect = np.zeros((n,n), dtype = float)
        unique_labels = np.unique(labels)
        for label in unique_labels:
            active_indices = np.nonzero(labels == label)                   # The indeces of where pred_labels equals label 
            active_subsample_indices = subsample_indices[active_indices]   # The rows of X where pred. is label
            for i, ind in enumerate(active_subsample_indices):      
                connect[ind,active_subsample_indices[i:]] = 1.0            # For a given active index i we do : d(i,j) & d(j,i) += 1 
                connect[active_subsample_indices[i:],ind] = 1.0            # for all j coming after i in active.ss. indices
        np.add(numerator, connect, numerator)                              # Sum the connectivity matrices         
        return numerator

    def update_denominator(denominator, subsample_indices):
        """
        inputs: 
                denominator - matrix dim n*n; sum of indication matrices
                ss_indices  - vector of dim ~pn of choses indices for current subsample
                indicator   - indicator matrix for current subsample

        output:             - added ones to all (i,j) in ss_indices 
            
        """
        indicator = np.zeros((n,n), dtype = float)
        unique_indices = np.unique(subsample_indices)
        for i, ind in enumerate(unique_indices):          
            indicator[ind,unique_indices[i:]] = 1.0      # We choose an index i, and for all other subsampled indeces j 
            indicator[unique_indices[i:],ind] = 1.0      # we set d(i,j) and d(j,i) to one
        np.add(denominator, indicator, denominator)      # Sum the indicator matrices
        return denominator

    PACs = {}
    
    X = feature_df.to_numpy()
    preprocessor = pre_processing()
    X = preprocessor.fit_transform(X)
    n,m = np.shape(X)
    for model in models:
        numerator   = np.zeros((n,n), dtype = float)         # We calculate the consensus matrix from the numerator 
        denominator = np.zeros((n,n), dtype = float)         # and denominator matrices i.e the sums of the connectivity 
        consensus   = np.zeros((n,n), dtype = float)         # and identicator matrices, respectively
                                                    
        subsample_size = int(np.floor(p*n))                
        for i in range(k):
            model_ = clone(model)                            # Clone model and if possible set a random_state
            try: 
                s = np.random.randint(1e3)
                model_.random_state = s
                if verbose:
                    print(f'At iteration {i}, with random state {s}')
            except AttributeError: 
                print("No random state attribute")
                pass
            subsample_indices = np.random.randint(low = 0, high = n, size = subsample_size)
            X_ = X[subsample_indices,:]                      # Our subsampled data   
            model_.fit(X_)                                   # Fit the clusterer to the data
            try:                                             # Return the predicted labels
                pred_labels = model_.labels_
            except AttributeError:
                try: 
                    pred_labels = model_.predict(X_)
                except AttributeError:
                    print("Model has neither predict nor labels_ attr.")   
                    raise AttributeError

            #  Now to update the numerator and denominator matrices
            numerator    = update_numerator(numerator, pred_labels,subsample_indices)
            denominator  = update_denominator(denominator,subsample_indices)

            assert(np.all(numerator<=denominator))
            
        assert(np.all(denominator != 0))
        np.divide(numerator, denominator, consensus, dtype = float)
        consensus = consensus.flatten()     # Consensus is now a 1D vector of (hopefully) mostly ones and zeros

        ecdf = ECDF(consensus)              # The empirical cumulative distribution function
        plt.plot(ecdf.x, ecdf.y)
        PACs[model] = ecdf(Q[1])-ecdf(Q[0]) # PAC values for the different models
    plt.legend(models)
    return PACs


def run_clustering(X_,models, clusters):
    # Run clustering and return the metrics and the predicted labels for each model
    predicted_labels = {}
    columns  = ['Clusters','Model','S', 'DB', 'CH']
    metrics_df = pd.DataFrame(columns = columns)
    model_names = [model.__class__.__name__ for model in models]
    shape = (len(model_names),len(columns)-2)
    metrics_df['Clusters'] = pd.Series(clusters, dtype= int)
    metrics_df['Model'] = pd.Series(model_names, dtype= "string")
    metrics = np.ndarray(shape= shape)
    clustering_metrics = [silhouette_score, davies_bouldin_score, calinski_harabasz_score]
    for i,model in enumerate(models):
        model.fit(X_)
        try:
            pred_labels = model.labels_
        except AttributeError:
            pass
        try: 
            pred_labels = model.predict(X_)
        except AttributeError:
            pass

        metrics[i,:] = [m(X_,pred_labels) for m in clustering_metrics]
        predicted_labels[model] = pred_labels

    metrics_df['S'] = metrics[:,0]
    metrics_df['DB'] = metrics[:,1]
    metrics_df['CH'] = metrics[:,2]

    return (metrics_df, predicted_labels)

def pre_processing(thrshld = 0.5, percent_variance = 0.8):
    preprocessor = Pipeline(steps=[
                        ('variance_filter', VarianceFilter(thrshld)),
                        ('scaler', RobustScaler()),
                        ('PCA', PCA(n_components=percent_variance, svd_solver = 'full'))])
    return preprocessor

def load_SEQ_data() -> pd.DataFrame:
    if exists('data/data.h5'):
        feature_df = pd.read_hdf('data/data.h5')
        label_df = pd.read_csv('data/labels.csv')
        feature_df = feature_df.iloc[:,1:]
        return label_df["Class"], feature_df.iloc[:,1:]  
    else:
        feature_df = pd.read_csv("data/data.csv")
        label_df = pd.read_csv('data/labels.csv')
        feature_df.to_hdf('data/data.h5',key = 'df', mode='w') 
        return label_df["Class"], feature_df.iloc[:,1:]  

def col_hist(df: pd.DataFrame, no_bins: int) -> None:
    # Plots histograms of the different features
    df_mean = df.mean(axis=0).transpose()
    df_var = df.var(axis=0).transpose()
    _, axes = plt.subplots(1,2)
    df_mean.hist(bins = no_bins, ax=axes[0], color = 'b')
    df_var.hist(bins = no_bins, ax=axes[1], color = 'y')
    plt.show()

def scree_plot(pca,thrshld):
    ratios = pca.explained_variance_ratio_
    ratio_sums = np.cumsum(ratios)
    comps = np.arange(1,len(ratios)+1)
    ratios = ratios/np.max(ratios)
    plt.plot(comps, ratios)
    plt.plot(comps, ratio_sums)
    plt.legend(["Ratio of explained variance, div by max","Cumulative sum of expl. var. in %"])
    plt.show()

def pair_plot(X,no_comps, labels = None):
    X_ = X.copy()
    X_ = X_[:,:no_comps]
    cols = ["PC%s" % _ for _ in range(1,no_comps+1)]
    df = pd.DataFrame(X_,columns=cols)
    if not isinstance(labels, type(None)):
        df["labels"] = labels
        _ = sns.pairplot(df, hue = "labels")
    else: 
        _ = sns.pairplot(df)
    
 
def metrics_plot(metrics: pd.DataFrame):
    no_models = metrics['Model'].nunique()
    models = metrics['Model'].unique()
    metric_cols = metrics.iloc[:,2:].columns
    # Plot the different metrics
    no_cols = metrics.shape[1]-2
    fig, axs = plt.subplots(no_models, no_cols)
    for i,model in enumerate(models):
        model_metrics = metrics[metrics['Model']==model]
        clusters = model_metrics['Clusters']
        for j,col in enumerate(metric_cols):
            metric_col = model_metrics[col]

            axs[i,j].plot(clusters, metric_col)
            axs[i,j].set_title((model,col))
    plt.show()

if __name__ == "__main__":
    main()