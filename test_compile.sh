#!/bin/bash
cd /app
cobc -x -free -I cobol/copybooks cobol/src/VALIDATE.cob -o cobol/bin/VALIDATE > /tmp/validate.log 2>&1
echo "VALIDATE exit code: $?" >> /tmp/validate.log

cobc -x -free -I cobol/copybooks cobol/src/TRANSACT.cob -o cobol/bin/TRANSACT > /tmp/transact.log 2>&1
echo "TRANSACT exit code: $?" >> /tmp/transact.log

cat /tmp/validate.log
echo "---"
cat /tmp/transact.log
