# Change log
## Version 0.0.4
+ Change .gitignore to Python template.
+ Synchronize with `hks_pylib` version 0.0.6.
+ Fix typo..
+ Change many error type and replace some of them to `hkserror`.
+ Future work:
    - Fix the error when a packet with invalid header (invalid or spoof size field).
    - Change `ChannelBuffer` and `PacketBuffer` to new style.
<!--- Commit at 02/05/2021 10:40:00 -->


## Version 0.0.3
+ Update `hks_pylib` to 0.0.5.
+ Change the name of some methods in modules `packet` and `secure_packet`.
+ Add highly identified exceptions in module `hks_pynetwork.errors`.
+ Beautify code.
+ Fix some errors. 