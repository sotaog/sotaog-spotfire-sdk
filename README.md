# README #

### Setup ###

The provided Spotfire Analysis example file has an embedded Python script to 
download and save as a datatable all of your wells and datapoints for those 
wells from the SOTAOG Public API.

Configure the script by setting the following script parameters

* `baseUrl`
* `credentials`

By default the script will pull all datapoints starting from Jan 1 2017. 
You can change this by modifying the script parameter `defaultStartTimestamp`.
