#!/bin/bash
folder=..

## Analyse the use of distinct file formats on this site and
## update d
fileformats="fileformats.md"
echo "# Distinct File Formats" >$fileformats
echo "Following are the distinct file formats used on this site: " >>$fileformats

for format in $(ls -R $folder |grep -e "^.*\.[a-zA-Z0-9]*$"|sed 's/\(.*\)\.\(.*\)/\2/'|sort|uniq)
do
   echo "* $format" >> $fileformats
done

