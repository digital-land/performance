# generated static site pages
DOCS_DIR=docs/

# data managed locally
DATA_DIR=data/

# generated data
DATASET_DIR=dataset/

# downloaded specification data
SPECIFICATION_DIR=specification/

# downloaded data from other sources
CACHE_DIR=var/cache/

DATA_FILES=\
	$(DATA_DIR)quality.csv\
	$(CACHE_DIR)organisation.csv\
	$(CACHE_DIR)local-planning-authority.csv\
	$(SPECIFICATION_DIR)award.csv\
	$(SPECIFICATION_DIR)cohort.csv\
	$(SPECIFICATION_DIR)fund.csv\
	$(SPECIFICATION_DIR)intervention.csv\
	$(SPECIFICATION_DIR)provision.csv\
	$(SPECIFICATION_DIR)project.csv\
	$(SPECIFICATION_DIR)project-organisation.csv\
	$(SPECIFICATION_DIR)role.csv\
	$(SPECIFICATION_DIR)role-organisation.csv

DOCS=\
	$(DOCS_DIR)index.html\
	$(DOCS_DIR)adoption/planx/index.html

all: $(DOCS) $(DATA_FILES)

$(DOCS_DIR)index.html:
	@mkdir -p $(DOCS_DIR)
	> $@
	
$(DOCS_DIR)adoption/planx/index.html: $(DATASET) bin/render.py 
	@mkdir -p $(dir $@)
	python3 bin/render.py > $@

$(CACHE_DIR)organisation.csv:
	@mkdir -p $(CACHE_DIR)
	curl -qfsL "https://files.planning.data.gov.uk/organisation-collection/dataset/organisation.csv" > $@

$(CACHE_DIR)local-planning-authority.csv:
	@mkdir -p $(CACHE_DIR)
	curl -qfsL 'https://files.planning.data.gov.uk/dataset/local-planning-authority.csv' > $@
            
$(SPECIFICATION_DIR)%:
	@mkdir -p $(SPECIFICATION_DIR)
	curl -qfsL 'https://raw.githubusercontent.com/digital-land/specification/main/specification/$(notdir $@)' > $@

clean::

clobber::
	rm -f $(DOCS) $(DATA)

init::
	pip install -r requirements.txt
	npm install svgo

server::
	python3 -m http.server -d $(DOCS_DIR)
