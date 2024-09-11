# newssurvey
**newssurvey** is a proof-of-concept Python 3.12 application to write a survey report about a question or concern using a single supported news site. The news site is used to conduct searches and read articles. Currently only the [MedicalXpress](https://medicalxpress.com/) news site is supported for medical topics, although some additional sites are planned for inclusion. Numerous calls are made to OpenAI LLMs to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

As of 2024, the estimated OpenAI API cost per report has been observed to be 1 to 6 USD. The cost varies by the number of source articles available for the submitted user query. The cost is approximately 1 USD per 100 source articles. Strictly speaking, the cost is unbounded and must be monitored and restricted via the [OpenAI usage dashboard](https://platform.openai.com/organization/usage). The generation time per report is expected to be under an hour, also depending on the number of source articles.

## Links
| Caption     | Link                                                 |
|-------------|------------------------------------------------------|
| Repo        | https://github.com/impredicative/newssurvey          |
| Changelog   | https://github.com/impredicative/newssurvey/releases |
| Package     | https://pypi.org/project/newssurvey                  |

## Approach
Each step in this workflow corresponds to an action taken by the LLM.

1. **Get search terms**: Search terms for the given user query and site are listed by the LLM. The user query is a question or concern applicable to the user chosen news site.
2. **Get filtered search results**: For each search term, a single page of search results is retrieved. More than one search type may be supported by the site, in which case all supported search types are used. Each result is composed of a title and possibly a blurb. The search results are filtered, one page at a time, for relevance by the LLM. This step is repeated for additional pages of search results until there are no relevant results for the page. After this, the full texts of all filtered search results are read.
3. **List section names**: The list of article titles is presented to the LLM, ordered by distance to the user query. The LLM provides a coherent single-level list of sections names.
4. **Get response title**: The LLM provides the response title using the list of section names.
5. **Rate articles for sections**: For each article, the LLM numerically rates on a scale of 0 to 100 how well the article can contribute to each section.
6. **Condense article by section**: For each article and section pairing, limited to ones with nonzero ratings, the LLM condenses the article text.
7. **Get text by section**: For each section, its condensed articles are concatenated together, ordered by their corresponding ratings, up to the maximum input context length of the LLM. The LLM formulates the text for each section. The section-specific citation numbers are replaced by globally consistent numbers.

The workflow is intended to be as simple as necessary, and without cycles between steps.

## Samples
These generated sample are available in HTML format. Their corresponding GitHub Flavored markdown versions are in the [samples](./samples/) directory.

| Source        | User query (shortened)                | Output title |
|---------------|---------------------------------------|--------------|
| medicalxpress | nutrition for anxiety                 | [Nutrition and Supplements for Anxiety Relief in Adults: Insights from Recent Research](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-11T02%3A51%3A12%20Nutrition%20and%20Supplements%20for%20Anxiety%20Relief%20in%20Adults%3A%20Insights%20from%20Recent%20Research.html) |
| medicalxpress | daytime drowsiness                    | [Managing Daytime Drowsiness: Understanding Causes and Solutions](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-11T02%3A20%3A37%20Managing%20Daytime%20Drowsiness%3A%20Understanding%20Causes%20and%20Solutions.html) |
| medicalxpress | northeast eastern equine encephalitis | [Eastern Equine Encephalitis: Prevention, Diagnosis, and Management in the Northeast](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-11T02%3A53%3A50%20Eastern%20Equine%20Encephalitis%3A%20Prevention%2C%20Diagnosis%2C%20and%20Management%20in%20the%20Northeast.html) |
| medicalxpress | vascular dementia in elderly          | [Holistic Management Strategies for Vascular Dementia in Elderly Patients](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-11T01%3A58%3A39%20Holistic%20Management%20Strategies%20for%20Vascular%20Dementia%20in%20Elderly%20Patients.html) |

As additional news sources are supported, samples based on them are intended to be added.

## Setup

### Common setup
* In the working directory, create a file named `.env`, with the intended environment variable `OPENAI_API_KEY=<your OpenAI API key>`, or set it in a different way.
* Continue the setup via GitHub or PyPI as below.

### Setup via GitHub using devcontainer
* Continue from the common setup steps.
* Clone or download this repo.
* Build and provision the defined devcontainer.

### Setup via GitHub manually
* Continue from the common setup steps.
* Clone or download this repo.
* Ensure that [`rye`](https://rye-up.com/) is installed and available.
* In the repo directory, run `rye sync --no-lock`.

### Setup via PyPI
* Continue from the common setup steps.
* Create and activate a Python 3.12 devcontainer or virtual environment.
* Install via [PyPI](https://pypi.org/project/newssurvey): `pip install -U newssurvey`.

## Usage
Only a single instance of the application must be run at a time, failing which throttles can aggressively be imposed by the source website and by OpenAI.

### Usage as application
In the simplest case, run `python -m newssurvey` to interactively start the application. You will be prompted for the necessary information.

For non-interactive use, the usage help is copied below:
```
$ python -m newssurvey -h
Usage: python -m newssurvey [OPTIONS]

  Generate and write a response to a question or concern using a supported news source.

  The progress is printed to stdout.

  A nonzero exitcode exists if there is an error.

Options:
  -s, --source TEXT               Name of supported news source. If not given, the user is prompted for it.
  -q, --query TEXT                Question or concern answerable by the news source. If a path to a file, the file
                                  text is read as text. If not given, the user is prompted for it.
  -m, --max-sections INTEGER RANGE
                                  Maximum number of sections to include in the response, between 10 and 100. Its
                                  recommended value, also the default, is 100.  [10<=x<=100]
  -f, --output-format TEXT        Output format of the response. It can be txt (for text), md (for markdown), gfm.md
                                  (for GitHub Flavored markdown), html, or json. If not specified, but if an output
                                  filename is specified via '--output-path', it is determined automatically from the
                                  file extension. If not specified, and if an output filename is not specified either,
                                  its default is txt.
  -o, --output-path PATH          Output directory path or file path. If intended as a directory path, it must exist,
                                  and the file name is auto-determined. If intended as a file path, its extension can
                                  be txt (for text), md (for markdown), gfm.md (for GitHub Flavored markdown), html,
                                  or json. If not specified, the output file is written to the current working
                                  directory with an auto-determined file name. The response is written to the file
                                  except if there is an error.
  -c, --confirm / -nc, --no-confirm
                                  Confirm as the workflow progresses. If `--confirm`, a confirmation is interactively
                                  sought as each step of the workflow progresses, and this is the default. If `--no-
                                  confirm`, the workflow progresses without any confirmation.
  -h, --help                      Show this message and exit.
```

Usage examples:

    $ python -m newssurvey -s medicalxpress -q ./my_medical_concern.txt -f html -o ~/output.html -c

    $ python -m newssurvey -s medicalxpress -q "safe strategies for weight loss" -f txt -o ~ -nc


## Cache
An extensive disk cache is stored locally to cache website and LLM outputs with a fixed expiration period. This is in the `[src]/newssurvey/.diskcache` directory. The expiration period is 1 week for website searches and 52 weeks for everything else, also subject to separate disk usage limits. To reuse the cache, rerun the same user query within this period. To bypass the cache, alter the user query, otherwise delete the appropriate cache subdirectory. Updates to the prompts will also bypass the cache.