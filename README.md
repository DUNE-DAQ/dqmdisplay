# dqmdisplay
Tools for on the spot Data Quality Monitoring. With dqmtools package it is possible to perform a number of basic checks for a given data file. 

### Quickstart
To run dqm_analyzer some external python libraries are needed, so one will need to create DBT working area with local python environment.
```bash
# Create a  DBT work area with local python environment
dbt-create <release> <workarea>
cd <workarea>
source env.sh

# Clone dqmtools here
git clone https://github.com/DUNE-DAQ/dqmdisplay.git
cd dqmtools
pip install [-e] .
```
After these steps everything should be ready and one can run
```bash
dqm_display /path/to/plots --port <available port>
```
Which will load up the event display. a. To view the events you need to set up a CERN socks proxy and have a local terminal connected.
To do this the plots are expected to be in subfolders: [`path/to/plots/EventDisplays`, `path/to/plots/pds_plots`, `path/to/plots/WIBTests` ].

# Accessing the event displays
Access from the NP02/4 machines is done through socks-proxy. To set this up a connection to `lxtunnel` 
```bash
ssh -N -D 8080 <your username>@lxtunnel.cern.ch
```
And then set up a suitable web proxy. For chrome users foxy proxy/similar is recommended. 