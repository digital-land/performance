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
	$(DATA_DIR)p153.csv\
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
	$(DOCS_DIR)adoption/planx/index.html\
	$(DOCS_DIR)award/index.html\
	$(DOCS_DIR)project/open-digital-planning/index.html\
	$(DOCS_DIR).nojekyll

all: $(DOCS) $(DATA_FILES)

$(DOCS_DIR)index.html:
	@mkdir -p $(DOCS_DIR)
	> $@

$(DOCS_DIR).nojekyll:
	@mkdir -p $(DOCS_DIR)
	touch $@
	
$(DOCS_DIR)adoption/planx/index.html: $(DATA_FILES) bin/render.py $(CACHE_DIR)organisation.csv
	@mkdir -p $(dir $@)
	python3 bin/render.py > $@

$(DOCS_DIR)award/index.html: $(DATA_FILES) bin/award.py $(CACHE_DIR)organisation.csv $(CACHE_DIR)point.svg $(CACHE_DIR)local-planning-authority.svg
	@mkdir -p $(dir $@)
	python3 bin/award.py > $@

$(DOCS_DIR)project/open-digital-planning/index.html: $(DATA_FILES) bin/open-digital-planning.py $(CACHE_DIR)organisation.csv
	@mkdir -p $(dir $@)
	python3 bin/open-digital-planning.py > $@

$(CACHE_DIR)organisation.csv:
	@mkdir -p $(CACHE_DIR)
	curl -qfsL "https://files.planning.data.gov.uk/organisation-collection/dataset/organisation.csv" > $@

$(CACHE_DIR)local-planning-authority.csv:
	@mkdir -p $(CACHE_DIR)
	curl -qfsL 'https://files.planning.data.gov.uk/dataset/local-planning-authority.csv' > $@
            
$(SPECIFICATION_DIR)%:
	@mkdir -p $(SPECIFICATION_DIR)
	curl -qfsL 'https://raw.githubusercontent.com/digital-land/specification/main/specification/$(notdir $@)' > $@

# https://www.gov.uk/government/statistical-data-sets/live-tables-on-planning-application-statistics
$(DATA_DIR)p153.csv: $(CACHE_DIR)P153.ods bin/p153.py $(CACHE_DIR)organisation.csv
	@mkdir -p $(dir $@)
	python3 bin/p153.py $(CACHE_DIR)P153.ods $@

$(CACHE_DIR)P153.ods:
	@mkdir -p $(CACHE_DIR)
	curl -qfsL 'https://assets.publishing.service.gov.uk/media/678654e4f041702a11ca0f53/Table_P153_Final.ods' > $@

$(CACHE_DIR)point.svg:
	curl -qfsL 'https://raw.githubusercontent.com/digital-land/choropleth/refs/heads/main/svg/point.svg' > $@

$(CACHE_DIR)local-planning-authority.svg:
	curl -qfsL 'https://raw.githubusercontent.com/digital-land/choropleth/refs/heads/main/svg/local-planning-authority.svg' > $@

clean::
	rm -rf var/

clobber::
	rm -f $(DOCS) $(DATA)

init::
	pip install -r requirements.txt
	npm install svgo

server::
	python3 -m http.server -d $(DOCS_DIR)
