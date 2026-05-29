$env:BPM_PASS = [System.Net.NetworkCredential]::new("", (Read-Host -AsSecureString "BPM password")).Password
docker-compose @args
