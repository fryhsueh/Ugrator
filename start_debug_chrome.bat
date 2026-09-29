@echo off
echo Starting Google Chrome with Remote Debugging on port 9225...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9225 --user-data-dir="C:\ChromeDebug_Ugrator" --no-first-run --no-default-browser-check
echo Chrome launched. Please log in to your tenant and open your IVR Canvas tab.
