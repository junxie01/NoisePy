# -*- coding: utf-8 -*-
"""
A python module to run surface wave Eikonal tomography
The code creates a datadbase based on hdf5 data format

:Dependencies:
    numpy >=1.9.1
    matplotlib >=1.4.3
    h5py 
    
:Copyright:
    Author: Lili Feng
    Graduate Research Assistant
    CIEI, Department of Physics, University of Colorado Boulder
    email: lili.feng@colorado.edu
    
:References:
    Lin, Fan-Chi, Michael H. Ritzwoller, and Roel Snieder. "Eikonal tomography: surface wave tomography by phase front tracking across a regional broad-band seismic array."
        Geophysical Journal International 177.3 (2009): 1091-1110.
    Lin, Fan-Chi, and Michael H. Ritzwoller. "Helmholtz surface wave tomography for isotropic and azimuthally anisotropic structure."
        Geophysical Journal International 186.3 (2011): 1104-1120.
"""
import numpy as np
import numpy.ma as ma
import h5py, pyasdf
import os, shutil
from subprocess import call
from mpl_toolkits.basemap import Basemap, shiftgrid, cm
import matplotlib.pyplot as plt
from matplotlib.mlab import griddata
import colormaps
import obspy
import field2d_earth

class EikonalTomoDataSet(h5py.File):
    
    def set_input_parameters(self, minlon, maxlon, minlat, maxlat, pers=np.array([]), dlon=0.2, dlat=0.2):
        """
        Set input parameters for tomographic inversion.
        =================================================================================================================
        Input Parameters:
        minlon, maxlon  - minimum/maximum longitude
        minlat, maxlat  - minimum/maximum latitude
        pers            - period array, default = np.append( np.arange(18.)*2.+6., np.arange(4.)*5.+45.)
        dlon, dlat      - longitude/latitude interval
        =================================================================================================================
        """
        if pers.size==0:
            # pers=np.arange(13.)*2.+6.
            pers=np.append( np.arange(18.)*2.+6., np.arange(4.)*5.+45.)
        self.attrs.create(name = 'period_array', data=pers, dtype='f')
        self.attrs.create(name = 'minlon', data=minlon, dtype='f')
        self.attrs.create(name = 'maxlon', data=maxlon, dtype='f')
        self.attrs.create(name = 'minlat', data=minlat, dtype='f')
        self.attrs.create(name = 'maxlat', data=maxlat, dtype='f')
        self.attrs.create(name = 'dlon', data=dlon)
        self.attrs.create(name = 'dlat', data=dlat)
        Nlon=(maxlon-minlon)/dlon+1
        Nlat=(maxlat-minlat)/dlat+1
        self.attrs.create(name = 'Nlon', data=Nlon)
        self.attrs.create(name = 'Nlat', data=Nlat)
        return
    
    def xcorr_eikonal(self, inasdffname, workingdir, fieldtype='Tph', channel='ZZ', data_type='FieldDISPpmf2interp', runid=0):
        create_group=False
        while (not create_group):
            try:
                group=self.create_group( name = 'Eikonal_run_'+str(runid) )
                create_group=True
            except:
                runid+=1
                continue
        group.attrs.create(name = 'fieldtype', data=fieldtype)
        inDbase=pyasdf.ASDFDataSet(inasdffname)
        pers = self.attrs['period_array']
        minlon=self.attrs['minlon']
        maxlon=self.attrs['maxlon']
        minlat=self.attrs['minlat']
        maxlat=self.attrs['maxlat']
        dlon=self.attrs['dlon']
        dlat=self.attrs['dlat']
        fdict={ 'Tph': 2, 'Tgr': 3}
        evLst=inDbase.waveforms.list()
        for per in pers:
            del_per=per-int(per)
            if del_per==0.:
                persfx=str(int(per))+'sec'
            else:
                dper=str(del_per)
                persfx=str(int(per))+'sec'+dper.split('.')[1]
            working_per=workingdir+'/'+str(per)+'sec'
            per_group=group.create_group( name='%g_sec'%( per ) )
            for evid in evLst:
                netcode1, stacode1=evid.split('.')
                try:
                    subdset = inDbase.auxiliary_data[data_type][netcode1][stacode1][channel][persfx]
                except KeyError:
                    print 'No travel time field for: '+evid
                    continue
                lat1, elv1, lon1=inDbase.waveforms[evid].coordinates.values()
                if lon1<0.:
                    lon1+=360.
                dataArr = subdset.data.value
                field2d=field2d_earth.Field2d(minlon=minlon, maxlon=maxlon, dlon=dlon, minlat=minlat, maxlat=maxlat, dlat=dlat, period=per, fieldtype=fieldtype)
                # return field2d
                Zarr=dataArr[:, fdict[fieldtype]]
                distArr=dataArr[:, 5]
                field2d.read_array(lonArr=np.append(lon1, dataArr[:,0]), latArr=np.append(lat1, dataArr[:,1]), ZarrIn=np.append(0., distArr/Zarr) )
                outfname=evid+'_'+fieldtype+'_'+channel+'.lst'
                field2d.interp_surface(workingdir=working_per, outfname=outfname)
                field2d.check_curvature(workingdir=working_per, outpfx=evid+'_'+channel+'_')
                field2d.gradient_qc(workingdir=working_per, evlo=lon1, evla=lat1, inpfx=evid+'_'+channel+'_', nearneighbor=True, cdist=None)
                field2d.evlo=lon1; field2d.evla=lat1
                # save data to hdf5 dataset
                event_group=per_group.create_group(name=evid)
                event_group.attrs.create(name = 'evlo', data=lon1)
                event_group.attrs.create(name = 'evla', data=lat1)
                appVdset     = event_group.create_dataset(name='appV', data=field2d.appV)
                reason_ndset = event_group.create_dataset(name='reason_n', data=field2d.reason_n)
                proAngledset = event_group.create_dataset(name='proAngle', data=field2d.proAngle)
                azdset       = event_group.create_dataset(name='az', data=field2d.az)
                bazdset      = event_group.create_dataset(name='baz', data=field2d.baz)
                Tdset        = event_group.create_dataset(name='travelT', data=field2d.Zarr)
                londset      = event_group.create_dataset(name='lonArr', data=field2d.lonArr)
                latdset      = event_group.create_dataset(name='latArr', data=field2d.latArr)
                # return field2d
        return
    
    def eikonal_stacking(self, runid=0):
        
        pers = self.attrs['period_array']
        minlon=self.attrs['minlon']
        maxlon=self.attrs['maxlon']
        minlat=self.attrs['minlat']
        maxlat=self.attrs['maxlat']
        dlon=self.attrs['dlon']
        dlat=self.attrs['dlat']
        Nlon=self.attrs['Nlon']
        Nlat=self.attrs['Nlat']
        group=self['Eikonal_run_'+str(runid)]
        
        for per in pers:
            per_group=group['%g_sec'%( per )]
            Treason=np.ones((Nlat-4, Nlon-4))
            Nmeasure=np.zeros((Nlat-4, Nlon-4))
            for evid in per_group.keys():
                event_group=per_group[evid]
                reason_n=event_group['reason_n'].value
                oneArr=np.ones((Nlat-4, Nlon-4))
                oneArr[reason_n!=0]=0
                Nmeasure+=oneArr
        return Nmeasure
                
        
        
        
    