#### Some references for troubleshooting and configuration
    - https://help.pythonanywhere.com/pages/SMTPForFreeUsers
    - https://support.google.com/a/answer/10685031?sjid=12353153684799953135-EU

#### Troubleshoot DNS records

    - [Best] https://toolbox.googleapps.com/apps/checkmx/check?domain=mourey.com&dkim_selector=
    - https://mxtoolbox.com/emailhealth/mourey.com/
    - https://powerdmarc.com/fr/spf-record-generator/

`@ 3600 IN TXT "v=spf1 a:pythonanywhere.com ~all"
@ 3600 IN TXT "v=spf1 include:_spf.google.com ~all"
@ 3600 IN TXT "v=spf1 include:philippe.mourey.com ~all"`

`v=spf1 include:pythonanywhere.com include:philippe.mourey.com`


