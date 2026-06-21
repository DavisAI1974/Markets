@echo off
cd /d E:\Markets
C:\Python313\python.exe _run_onset_coeffs.py --workers 4 > E:\Markets\_pipeline_logs\_onset_driver.out 2>&1
