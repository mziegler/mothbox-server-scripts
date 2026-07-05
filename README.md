# mothbox-server-scripts
Server scripts/configuration for Mothbox network

Does the following things:
1. Fetches photos from network-connected Mothboxes every night, saves them on local disc
2. Runs Mothbot_Process AI pipeline on new photos as they come in (at the end of each night)
3. Moves processed photos into cloud storage 

## To run:
* Create a user called "mb"
* Install rclone and run `rclone config` to set up the connection for photo storage
* Make sure all Mothboxes are reachable on the network, (the easiest way I've found is by using TailScale), and record them in mothbox-list.csv. Make sure that your server is properly set up to SSH into them; that the appropriate keys are set up on on both your server and the mothboxes. Edit your server's .ssh/config file so that the user on the mothboxes is "pi".
* Review the settings in mothboxServerConfig.py
* Clone this repository into /home/mb/mothbox-server-scripts

```
sudo cp /home/mb/mothbox-server-scripts/deploy/mothbox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mothbox.service
```
