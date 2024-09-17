# newssurvey
**newssurvey** is a proof-of-concept Python 3.12 application to write a survey report about a question or concern using a single supported news site. The news site is used to conduct searches and read articles. Currently only two sites are supported. Numerous calls are made to OpenAI LLMs, namely gpt-4o-mini and gpt-4o, to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

## Sources

The supported sources are:

| Name                                            | Type    | Observed LLM cost range per report in USD |
|-------------------------------------------------|---------|-------------------------------------------|
| [medicalxpress](https://medicalxpress.com/)     | medical | 1 to 6  |
| [physorg](https://phys.org/)                    | science | 1 to 19 |

The LLM cost per report varies by the number of source articles and output sections for the submitted user query. The cost is approximately 1 USD per 100 source articles per 10 output sections. Strictly speaking, the cost is unbounded and must be monitored and restricted via the [OpenAI usage dashboard](https://platform.openai.com/organization/usage). The generation time per report is expected to be under an hour, also depending on the number of source articles.

## Links
| Caption     | Link                                                 |
|-------------|------------------------------------------------------|
| Repo        | https://github.com/impredicative/newssurvey          |
| Changelog   | https://github.com/impredicative/newssurvey/releases |
| Package     | https://pypi.org/project/newssurvey                  |

## Approach
Each step in this workflow corresponds to an action taken by the LLM.

1. **Get search terms**: Search terms for the given user query and site are listed by the LLM. The user query is a question or concern applicable to the user chosen news site. Additional search terms are also obtained until convergence.
2. **Get filtered search results**: For each search term, a single page of search results is retrieved. More than one search type may be supported by the site, in which case all supported search types are used. Each result is composed of a title and possibly a blurb. The search results are filtered, one page at a time, for relevance by the LLM. This step is repeated for additional pages of search results until there are no relevant results for the page. After this, the full texts of all filtered search results are read.
3. **List section names**: The list of article titles is presented to the LLM, ordered by distance to the user query. The LLM provides a coherent single-level list of sections names. The list is then refined until convergence.
4. **Rate articles for sections**: For each article, the LLM numerically rates on a scale of 0 to 100 how well the article can contribute to each section.
5. **Condense article by section**: For each article and section pairing, limited to ones with nonzero ratings, the LLM condenses the article text.
6. **Get text by section**: For each section, its condensed articles are concatenated together, ordered by their corresponding ratings, up to the maximum input context length of the LLM. The LLM formulates the text for each section. The section-specific citation numbers are replaced by globally consistent numbers.
7. **Get response title**: The LLM provides the response title using the list of section names.

The workflow is intended to be as simple as necessary, and without cycles between steps.

## Limitations

Due to the LLM's context window limitation of 128K, only up to about 400 condensed articles can be used for writing a section. Efforts are made, of course, to use the most highly rated section-specific relevant articles that fit in this window.

## Samples
These generated sample are available in HTML format. Their corresponding GitHub Flavored markdown versions are also available in the [samples](https://github.com/impredicative/newssurvey/tree/master/samples) directory of the repository.<!-- Note: An absolute link is used because a relative link doesn't work in PyPI. -->


| Source        | User query (simplified)               | Output title |
|---------------|---------------------------------------|--------------|
| medicalxpress | nutrition for anxiety                 | [Nutritional Strategies and Supplements for Managing Anxiety in Adults](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-15T03%3A59%3A45%20Nutritional%20Strategies%20and%20Supplements%20for%20Managing%20Anxiety%20in%20Adults.html) |
| medicalxpress | daytime drowsiness                    | [Understanding and Addressing Daytime Drowsiness: Causes, Strategies, and Solutions](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-15T05%3A27%3A48%20Understanding%20and%20Addressing%20Daytime%20Drowsiness%3A%20Causes%2C%20Strategies%2C%20and%20Solutions.html) |
| medicalxpress | acid reflux treatments            | [Comprehensive Approaches to Managing GERD: From Lifestyle Changes to Emerging Treatments](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-15T06%3A04%3A01%20Comprehensive%20Approaches%20to%20Managing%20GERD%3A%20From%20Lifestyle%20Changes%20to%20Emerging%20Treatments.html) |
| physorg       | dark matter theories            | [Comprehensive Exploration of Dark Matter Theories and Alternatives](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-17T15%3A36%3A56%20Comprehensive%20Exploration%20of%20Dark%20Matter%20Theories%20and%20Alternatives.html) |
| physorg       | multiverse theories            | [Exploring Multiverse Theories: Foundations, Evidence, and Implications](https://html-preview.github.io/?url=https://github.com/impredicative/newssurvey/blob/master/samples/2024-09-17T15%3A38%3A34%20Exploring%20Multiverse%20Theories%3A%20Foundations%2C%20Evidence%2C%20and%20Implications.html) |


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
Usage can be as a command-line application or as a Python library.

### Usage considerations
* Refining the query text over a few iterations is often essential for receiving a sufficiently tailored response.
* Only a single instance of the application must be run at a time, failing which throttles can aggressively be imposed by the source website and by OpenAI. This is also enforced at the application-level by the use of a lock file.

### Usage as application
In the simplest case, run `python -m newssurvey` to interactively start the application. You will be prompted for the necessary information.

For non-interactive use, the usage help is copied below:
```
$ python -m newssurvey -h
Usage: python -m newssurvey [OPTIONS]

  Generate and write a response to a question or concern using a supported news source.

  A single instance of this method is enforced.

Options:
  -s, --source TEXT               Name of supported news source. If not given, the user is prompted for it.
  -q, --query TEXT                Question or concern answerable by the news source. If a path to a file, the file
                                  text is read as text. If not given, the user is prompted for it.
  -m, --max-sections INTEGER RANGE
                                  Maximum number of sections to include in the response, between 5 and 100. Its
                                  recommended value, also the default, is 100.  [5<=x<=100]
  -f, --output-format TEXT        Output format of the response. It can be txt (for text), md (for markdown), gfm.md
                                  (for GitHub Flavored markdown), html, pdf, or json. If not specified, but if an
                                  output filename is specified via '--output-path', it is determined automatically
                                  from the file extension. If not specified, and if an output filename is not
                                  specified either, its default is txt.
  -o, --output-path PATH          Output directory path or file path. If intended as a directory path, it must exist,
                                  and the file name is auto-determined. If intended as a file path, its extension can
                                  be txt (for text), md (for markdown), gfm.md (for GitHub Flavored markdown), html,
                                  pdf, or json. If not specified, the output file is written to the current working
                                  directory with an auto-determined file name. The response is written to the file
                                  except if there is an error.
  -c, --confirm / -nc, --no-confirm
                                  Confirm as the workflow progresses. If `--confirm`, a confirmation is interactively
                                  sought as each step of the workflow progresses, and this is the default. If `--no-
                                  confirm`, the workflow progresses without any confirmation.
  -h, --help                      Show this message and exit.
```

Usage examples:

    $ python -m newssurvey -s medicalxpress -q "safe strategies for weight loss" -f txt -o ~ -nc

    $ python -m newssurvey -s medicalxpress -q ./my_detailed_medical_concern.txt -f html -o ~/output.html -c

    $ python -m newssurvey -s physorg -q ./my_science_query.txt -f pdf -o ./work/ -m 10

### Usage as library

```python
>>> from newssurvey.newssurvey import generate_response
>>> import inspect

>>> print(inspect.signature(generate_response))
(source: str, query: str, max_sections: int = 100, output_format: Optional[str] = 'txt', confirm: bool = False) -> newssurvey.types.Response

>>> print(inspect.getdoc(generate_response))
```
```text
Return a response for the given source and query.

The returned response contains the attributes: format, title, response.

The progress is printed to stdout.

Params:
* `source`: Name of supported news source.
* `query`: Question or concern answerable by the news source.
* `max_sections`: Maximum number of sections to include in the response, between 5 and 100. Its recommended value, also the default, is 100.
* `output_format`: Output format. It can be txt (for text), md (for markdown), gfm.md (for GitHub Flavored markdown), html, pdf, or json. Its default is txt.
* `confirm`: Confirm as the workflow progresses. If true, a confirmation is interactively sought as each step of the workflow progresses. Its default is false.

If failed, a subclass of the `newssurvey.exceptions.Error` exception is raised.
```

## Cache
An extensive disk cache is stored locally to cache website and LLM outputs with a fixed expiration period. This is in the `[src]/newssurvey/.diskcache` directory. The expiration period is 1 week for website searches and 52 weeks for everything else, also subject to separate disk usage limits. To reuse the cache, rerun the same user query within this period. To bypass the cache, alter the user query, otherwise delete the appropriate cache subdirectory. Updates to the LLM prompts will also bypass the cache.

The LLM is prompted to always output in a basic text format. Following this, the text is structured into the user-requested output format without using the LLM. Rewriting the output into a new format is therefore possible offline until the earliest cache expiration, typically for 1 week.

## Disclaimer

<sub>This software is provided as a proof-of-concept application and is distributed under the LGPL license. It is offered without any guarantees or warranties, either expressed or implied, including but not limited to the implied warranties of merchantability, fitness for a particular purpose, or non-infringement.</sub>

<sub>Users are responsible for ensuring that they have the necessary API keys, permissions, and access to third-party services such as the OpenAI API, which are required for full functionality. The costs associated with using the OpenAI API, including those outlined in this documentation, are subject to change and must be monitored independently by the user.</sub>

<sub>The software relies on third-party services and content from news sites. The availability, accuracy, or relevance of content from these external sources cannot be guaranteed, nor can the continued accessibility of these services be ensured in the future. The accuracy and reliability of reports generated by the software depend on the quality of input queries, availability of articles, and the performance of language models, all of which are subject to change and influenced by external factors beyond the control of the software.</sub>

<sub>While efforts have been made to optimize the performance and output of this software, users should independently verify any information generated, particularly if it is intended for use in professional, medical, scientific, technical, legal, or other high-stakes contexts. Use of this software is at your own risk. This software should not be used as the sole basis for any serious, life-impacting decisions. Always consult relevant professionals or authoritative sources directly for such purposes.</sub>

<sub>By using this software, you agree that its developers and contributors shall not be held liable for any damages, costs, or losses arising from its use, including but not limited to direct, indirect, incidental, consequential, or punitive damages. Users are encouraged to thoroughly review its source code to understand the workings of the application and assess its suitability for their intended use.</sub>

<sub>The authors do not claim ownership of any content generated using this software. Responsibility for the use of any and all generated content rests with the user. Users should exercise caution and due diligence to ensure that generated content does not infringe on the rights of third parties.</sub>

<sub>This disclaimer is subject to change without notice. It is your responsibility to review it periodically for updates.</sub>