## Bradley Fargo

# IoT Device-to-Device Communication Hands On Project Notes

This notes page is meant to record what I did to start the hands-on project about Device to Device Communication between a raspberry Pi and a laptop.

# Step 0:

Figure out what devices I want and what communication protocols and hardware I will use to communicate.

I chose RN-2903-PICTAIL (available from Microchip Technology’s online store). This is a chip that connects to an antenna and plugs in via Micro-usb to USB cable. This can be connected to a Raspberry Pi and to a laptop. I purchased two.

I also bought a LoRa Hat to play around with (LoRa / GPS Hat Long distance wireless 915Mhz Lora and GPS Expansion Board for Raspberry Pi). This has yet to come in.

## Pi Setup:

From Abde I borrowed a Raspberry Pi 3 Model B+. Setting it up requires a 32 GB sd card as well. 

To look at devices do   
`lsblk -o NAME,SIZE,LABEL,MOUNTPOINT`  
And pick out the SD card or microSD card you have plugged in, for me it was under \`sda\`. Then you might have to mount it. I used the \`rpi-imager\` tool (downloaded via pacman package manager) running as sudo. It makes available a GUI where you can select what type of Pi you have, and what OS you want on it, and the storage location of the microSD card, and image it. There were some additional settings, where you can include a custom user, so I made the dori user. It changes the name of the machine to dori.

But long story short I put Raspbian on it. Next I ran the \`lsblk\` command again, this time looking for the bootfs part of the microSD card. I mounted it by making a /mnt/boot directory and running \`sudo mount /dev/sda1 /mnt/boot\`

Once its mounted I can make files on it, so I ran \`sudo touch /mnt/boot/ssh\` which tells the OS to enable SSH on boot.

I also made a wpa\_supplicant.conf file in the same directory, so \`sudo touch /mnt/boot/wpa\_supplicatn.conf\` and filled in  
\`country=US  
ctrl\_interface=DIR=/var/run/wpa\_supplicant GROUP=netdev  
update\_config=1

network={  
    ssid="YourWiFiName"  
    psk="YourWiFiPassword"  
}\`

Then I unmounted with \`sudo umount /mnt/boot\`

So now the Pi, when it powers on I can ssh in. To check if it’s up I can do \`ping dori.local\` and then if I get a response back, I can connect with \`ssh [dori@dori.local](mailto:dori@dori.local)\`.

The setup I did is plugged in a little portable screen, a little portable keyboard and a bluetooth dongle mouse, and then ssh-ed in and did \`touch \~/Desktop/hey\` and saw a new file appear called hey on the desktop, the rm-ed it. Got a working Raspberry Pi.

Next I’ll need to make sure it has some dependencies and software loaded on it. But we’ll get to that later. I used ChatGPT 5 to help out in loading up raspbian on the Pi.

## Laptop Setup:

My personal laptop is loaded up with manjaro linux. I use the pacman package manager. To replicate this project one would need to make sure whatever package manager you use (assuming linux) has a couple things installed.

# Step 1:

Establish Communication directly between the Raspberry Pi and the laptop.

There are three methods I am using to communicate here. The goal is to get a ping using each one. Then after that, I will design some tests and experiments. But we need to be able to make some sort of connection first.

## WiFi:

So there are two protocols to consider here, one is the “recommended” option, WiFi Direct. The other is WiFi Adhoc. Abde mentioned Adhoc and recommended it I believe so I will start with this. It is an older protocol, so Windows 11 doesn’t support Adhoc. Fortunately I am using Linux, so it represents a good place to start.

### Adhoc:

First I will set up the pi.

I ssh into the pi (i’m using the kitty terminal cause i am using the hyprland desktop compositor, and the $TERM variable is set to xterm-kitty which the Pi doesn’t recognize, so i basically set the $TERM variable to xterm then nano works). I also got annoyed with this later and did \`sudo apt install kitty-terminfo\` on the pi to make it so the pi knows what to do with xterm-kitty as the TERM variable when I use nano.

I run \`sudo nano /boot/firmware/wpa\_supplicant.conf\`

I’ll ssh in and update the wifi supplicant.conf file that we made earlier with some changes. Basically the network section, replace it with \`  
\`  
network={  
    ssid=”PiAdhoc”  
    mode=1  
    frequency=2462  
    key\_mgmt=NONE  
}  
\`  
So the mode \= 1 part is about putting it in ad-hoc mode (IBSS)  
The frequency is about the channel, in this case 2462 specifies channel 11\.

Ok then I reboot the machine, but the pi remembers my wifi network, so I hit the checkbox to make the machine not autoconnect to beigescaffold.

After that I tried iwconfig and it looked like adhoc wasn’t set up. It looks like NetworkManager is controlling the wifi. I checked \`sudo systemctl status NetworkManager\` and saw it was active (running). So first thing I have to do is stop and disable it, so \`sudo systemctl stop NetworkManager\` then \`sudo systemctl disable NetworkManager\`.

Another thing to do is give the network a static IP.  
So \`sudo nano /etc/dhcpcd.conf\`  
And add to the bottom   
\`  
Interface wlan0  
  Static ip\_address=192.168.12.1/24  
  Nohook wpa\_supplicant  
\`  
Hmm this is getting complicated. I later got rid of the dhcpcd.conf file. The idea is to do this manually.

So first we want to stop the NetworkManager  
\`sudo systemctl stop NetworkManager\`

Then bring the WiFi interface up in ad-hoc mode  
\`sudo ip link set wlan0 down\`  
\`sudo iw dev wlan0 set type ibss\`  
\`sudo ip link set wlan0 up\`

Create and join the ad-hoc network  
\`sudo iw dev wlan0 ibss join PiAdhoc 2437\` thats the channel frequency for channel 6

Assign a static IP  
\`sudo ip addr add 192.168.12.1/24 dev wlan0\`

To look at what we did  
\`iw dev wlan0 info\`  
\`ip addr show wlan0\`

Ok now on to the laptop

To see the WiFi interface name:  
\`nmcli device status\`

I can see my wifi interface name is wlp0s20f3  
\`  
sudo systemctl stop NetworkManager (to stop the nm, which deals with wifi access points)  
\`  
\`  
sudo ip link set wlp0s20f3 down  
sudo iw dev wlp0s20f3 set type ibss  
sudo ip link set wlp0s20f3 up  
sudo iw dev wlp0s20f3 ibss join PiAdhoc 2437  
sudo ip addr add 192.168.12.2/24 dev wlp0s20f3  
\`  
so next we test the connection  
\`  
ping 192.168.12.1  
\`  
If that gets a response, there is a connection.

I can also ssh in using this connection, so   
\`ssh dori@192.168.12.1\`

it works yay\!

If I want to go back to normal, on both machines I start the Network Manager  
\`sudo systemctl start NetworkManager\`  
And I can remove the ad-hoc IP   
\`sudo ip addr flush dev wlan0\`  
\`sudo ip addr flush dev wlp0s20f3\` for the laptop

Ok now if I want to replicate this process. Starting from the beginning.

So first I want to disconnect from my WiFi and make it so I do not autoconnect.

Before turning off the wifi I run \`nmcli connection show\` to see the known connections.

I see the current one is green and named beigescaffold (that's my WiFi access point's name).

so I turn the wifi off with \`nmcli radio wifi off\` and then turn off autoconnect for this network.

So \`nmcli connection modify "beigescaffold" connection.autoconnect no\`

This makes it so when I run \`nmcli radio wifi on\` turning the wifi back on I see that it is Disconnected.

Ok so I made a bash script.

If I were to ssh into the pi and run the script I’d have to include a nohup command that ends with & so that when ssh drops the script keeps running. 

\`  
`ssh dori@dori.local "nohup sudo /home/dori/adhoc.sh start pi &"`  
`` ` ``

`First I need to copy the script over so I did`  
`` ` ``  
`scp /home/dori/d2d/adhoc.sh dori@dori.local:/home/dori/d2d/`  
`` ` ``

`` And then in the pi `chmod +x ~/d2d/adhoc.sh` ``

`Ok so now I want there to be a timeout, this command accomplishes that ->`  
`` ` ``  
`ssh dori@raspberrypi.local "nohup bash -c 'sudo /home/dori/d2d/adhoc.sh start pi && sleep 180 && sudo /home/dori/d2d/adhoc.sh stop' > /home/dori/adhoc.log 2>&1 &"`  
`` ` ``  
`But ok now if I want to do a timeout in the script itself I could do that with like a —-timeout flag. I added that to the script, so`   
`` `sudo ./adhoc.sh start pi --timeout 10` ``  
`will start a timeout of 10 seconds`

`Honestly, the idea of a script to make this process repeatable is a good idea, but I got there by reading suggestions for next steps in the chatbot prompt responses I was using to figure out how to do a ping manually using WiFi Ad-hoc.`

### Direct:

Right now I won’t be doing a WiFi Direct connection. Maybe something for later.

## Bluetooth:

Ok to start I’ll want to make sure both devices have some tools  
\`sudo apt install \-y bluez bluez-tools bluetooth\` on the pi  
\`sudo pacman \-Syu bluez bluez-utils\` on the manjaro laptop

Ok now on the laptop

Bluetoothctl   
This opens up a different command line interface, like a shell where the text is blue. I entered a couple of things on that interface.

\[bluetoothctl\] power on  
\[bluetoothctl\] agent on  
\[bluetoothctl\] default-agent  
\[bluetoothctl\] scan on

Basically the laptop is the BT client (initiates pairing). The Pi is the BT server (listens and accepts pairing)

On the Pi, to mess with bluetoothctl, I had an rfkill softblock on the Bluetooth (to see if you do, do  \`rfkill list all\` I did \`sudo rfkill unblock bluetooth\` to unblock it, restarted the bluetooth service in systemctl and retried the bluetoothctl commands.

\[bluetooth\] power on  
\[bluetooth\] agent on  
\[bluetooth\] default-agent  
\[bluetooth\] discoverable on  
\[bluetooth\] pairable on

On the laptop I see a device pop up with the right name:

\[NEW\] Device B8:27:EB:D6:9C:95 dori

Then I do on the laptop  
 \[bluetoothctl\]\> pair B8:27:EB:D6:9C:95  
Attempting to pair with B8:27:EB:D6:9C:95  
\[CHG\] Device B8:27:EB:D6:9C:95 Connected: yes  
Request confirmation  
\[agent\] Confirm passkey 672536 (yes/no): yes

There’s some confusing input with confirm passkey, i think hitting yes when necessary is what to do here.

Next I do the following commands:  
trust B8:27:EB:D6:9C:95  
connect B8:27:EB:D6:9C:95

The bluetoothctl changes to \[dori\] so i think it worked

Now do \`devices\` in bluetoothctl to see the Devices paired  
\`devices Connected\` to see only those connected

For later connections can skip to the connect MACADRESS part

For info on specific device do \`info \<MAC\>\`

Anyway I did a bluetooth connection via bluetoothctl. This is a control-channel connection (for audio, keyboard etc).

I want to be able to do more than play audio, I want to be able to ping and transfer files. This is to demonstrate a connection and take down metrics in different conditions.

There's a way to open a serial port via rfcomm but that seems to be a deprecated tool in modern bluetooth libraries. 

So I’ll use a PAN (Personal Area Network) (the networking profile that BT uses to do IP style things), a NAP (Network Access Point) (the server \[the pi\] that offers a bridge), a PANU (User) (the client \[laptop\] that connects) and a network interface which is created on each side (bnep0).

I’ll use bnep0 like using WiFI to ping or scp is the plan. That’s a virtual network interface (bnep0) that appears when a NAP profile is started and a PANU (client) connects to it.

Start the NAP service  
\`sudo bt-network \-s nap br0 &\`  
This waits for a client to connect and will create bnep0

I ran into a problem where BlueZ is a program that I’m depending on to navigate bluetooth from the command line, but there’s optional network tools which my package manager does not make available via the typical repo. That would be bt-network. But basically I tried a couple different things to install this tool and failed so I’m doing a workaround. The following is pasted from a chatbot:  
“

## **🧩 Option 2 — Run bluetoothd itself as a NAP (no helper needed)**

Both BlueZ 5.70+ and your build support the `--nap` flag directly.

### **On the Pi (server)**

sudo systemctl stop bluetooth  
sudo /usr/lib/bluetooth/bluetoothd \--nap &

That exposes the Network Access Point profile.  
 When the laptop connects, `bnep0` appears automatically.

### **On the laptop (client)**

You can initiate the PAN connection manually through `bluetoothctl`:

bluetoothctl  
\[bluetooth\]\# power on  
\[bluetooth\]\# agent on  
\[bluetooth\]\# default-agent  
\[bluetooth\]\# pair \<Pi-MAC\>  
\[bluetooth\]\# trust \<Pi-MAC\>  
\[bluetooth\]\# connect \<Pi-MAC\>  
\[bluetooth\]\# menu network  
\[bluetooth\]\# connect nap  
\[bluetooth\]\# back  
\[bluetooth\]\# quit

Now run  
ip link show

and you should see `bnep0`.

Then assign IPs and test:

\# On Pi  
sudo ip addr add 192.168.44.1/24 dev bnep0  
sudo ip link set bnep0 up

\# On laptop  
sudo ip addr add 192.168.44.2/24 dev bnep0  
sudo ip link set bnep0 up

\# Test  
ping 192.168.44.1

🎉 That gives you a full “pingable” Bluetooth network with **no extra binaries**.  
“  
So I’ll try that next time I work on this.  
	  
Ok it is that next time I work on this. :) 

I have the Pi and the laptop on. I have the pi available and open to ssh, so I ssh in from my machine and run commands on it. I also have a keyboard, mouse and monitor connected to it so I can enter commands manually. SSH is fine for now.

Anyway I run bluetoothctl on the laptop. I already connected to the pi, so I do \`devices\` and bluetoothctl lists the paired devices. I see the MAC Address for dori and do \`connect B8:27:EB:D6:9C:95\` It works\! Yay.

But I don’t actually want to be connected yet so \`disconnect\`

Now. On the pi, I do \`which bluetoothd\` which is at /usr/sbin/bluetoothd.  
I do sudo \`systemctl stop bluetooth\`  
Ok so actually how about   
\`sudo bt-network \-s nap pan0\`  
I get NAP server registered.

You can add a & to background the task on the pi (useful cause I’m sshing and didn’t want to make another shell instance)

Now on the laptop I can just do   
\`connect MAC\_PI\`  
and then  
\`nmcli device\`   
and there should be  
A bt type device that appears.

\`sudo nmcli connection add type bluetooth con-name bt-pan ifname "B8:27:EB:D6:9C:95" bluetooth.type nap\`

Hmm ok so I ran into dependency problems but also different problems stemming from a lack of familiarity with bluetoothctl. I tried Claude next. I think I tried the high powered model because it gave me quite a bit.

I think the happy medium of what I actually need is something much less than provided, but I tried the scripts and it seemed to function. I haven’t tried it when turning off all other networks. And I super don’t understand the code provided as I haven’t even read it. I committed it to the github where I’m keeping stuff though.

## LoRa (not LoRaWAN):

Ok to start with. I plugged in the pi, connected it to (my parents this time) wifi and ran   
\`ls /dev/tty\*\`  
To look for the tty representing the thing I plugged in. I saw a bunch of ttys named with just numbers, and one on each with the name /dev/ttyACM0. So this is my device, or at least how to communicate with it.

Tty means teletype (so like text terminal). /dev/ttyACM- is a USB serial device using ACM (Abstract Control Model) which is for usb modems or microcontrollers. It lets me talk to the board with an antenna I plugged in.

Ok so now I need to communicate over serial console with the RN2903 USB Modem. I could use screen or minicom or picocom to do that apparently. I’ll use screen.

So now I try \`screen /dev/ttyACM0\`

I get \[screen is terminating\] as a response.

So it might be that I’m using the dori user, who is not of a privileged user group that can interact with this device.

(On pi \`sudo usermod \-aG dialout $USER\`)

So on laptop I’d do \`sudo usermod \-aG uucp dori\`  
Then \`sudo reboot\` to let the group change apply, then  
\`screen /dev/ttyACM0\` and right after I plug it in I get a hanging black screen, a little after I might get \[screen is terminating\] if I kill the hanging process and try again.

I replugged the pi and ran \`dmesg | tail \-n 20\` to look at the last couple things that happened and where logged device wise  
I ran \`ls \-l /dev/ttyACM\*\` to see the acm devices because in the dmesg log I noticed an ACM1 and ACM0 mentioned.

Can do \`sudo fuser /dev/ttyACM1\` when acm1 is being connected to (this time I see a \+ as the only thing on the screen

I installed picocom to check out the connection a bit more so

\`lsof | grep ttyACM\`  
To look at ongoing processes related to the ACM tty, If you unplug while a connection is ongoing a process continues on the computer, you can \`kill \<PID\>\` these processes if you want or \`killall screen\` to kill all screen connections (or picocom if youre using that).

\`sudo picocom \-b 9600 /dev/ttyACM1\`  
(can view the parity (should be none) databits (8) stopbits (1) etc

I’m trying different baud rates, I think 57600 is the typical one but I get an artifact (+ at the top left). Idk troubleshooting.

So this type sub in 57600 for the \-b argument.  
Still no response.  
It might be line endings, apparently the RN2903 expects commands ending with CR+LF, enable local echo to see what i’m typing in picocom

\`picocom \-b 57600 \--echo /dev/ttyACM2\`

So im learning a bit about picocom and minicom, config looks good

Ok force control. When I send a break signal in picocom I get “\*\*\* flow: RTS/CTS \*\*\*”  
So  
I  run \`stty \-F /dev/ttyACM0\` to check current port settings

\`stty \-F /dev/ttyACM0 57600 \-crtscts \-ixon \-ixoff\`  
To disable hardware flow control at the system level

Hmm that was the wrong thing, I tried touching test pins to ground with a paper clip and observe some leds blink when I do that.

At some point I got hex output in a txt file from the device.  
 It wasn’t visible from cat but hexdump showed it

I also see artifacts sometimes when I touch pins and do a picocom

I had claude write and iterate on a bash script to try and test this process. I got a small garbled response several times but it was while touch a pin on the board with a wire, and I wasn’t able to get consistent responses while doing this. This is complicated by the fact that touching a pin might have some effect or no effect, sometimes the leds blink and the ACM number changes.

Iterations of the script i put in the github

Anyway im just going to flash it with new firmware

So download LoRa….. .run for linux, 

Download and run it to install at 

/root/Microchip/LoRaSuite

Downloaded from : [www.microchip.com/Developmenttools/ProductDetails.aspx?PartNO=dv164140-1](http://www.microchip.com/Developmenttools/ProductDetails.aspx?PartNO=dv164140-1)

Hmm ok starting over, trying to connect on windows machine. I am able to do it over the COM 5 interface and \`sys get ver\` gets reasonable output using tera term ([https://github.com/TeraTermProject/teraterm/releases](https://github.com/TeraTermProject/teraterm/releases)). I think I had to adjust the line endings to get a reasonable response from the plugged in device on windows, selecting the right COM port or whatever.

That’s how far I got. Now I need to be able to access the device on linux. I don’t think I need to reset it or anything.

