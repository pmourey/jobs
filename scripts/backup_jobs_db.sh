#!/bin/bash
#
# Script de sauvegarde de la base jobs (SQLite)
#
HOME_DIR="/home/pmourey"
cp -p ${HOME_DIR}/jobs/instance/jobs.sqlite3 ${HOME_DIR}/backups/jobs_$(date +"%Y%m%d").sqlite3