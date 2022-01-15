# Some packages have trouble installing "cryptography" python file, since it depends on Rust which
# has questionable support on raspis
FROM debian:latest

# RUN apt-get update && apt-get -y install build-essential libssl-dev libffi-dev python-dev rust && rm -rf /var/lib/apt/lists/* 
RUN apt-get update && apt-get -y install python3 python3-pip python3-setuptools dnsutils && rm -rf /var/lib/apt/lists/*
RUN pip3 install dns-lexicon

CMD echo "Keeping fresh A records for: $SUBDOMAINS" && \ 
    while true; do \
      for n in $SUBDOMAINS; do \
	    lexicon hover update mkr.house A --name $n --content $(dig +short myip.opendns.com @resolver1.opendns.com); sleep 5; \
      done; \
      sleep 3600; \
    done

