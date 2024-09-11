# newssurvey
**newssurvey** is a Python 3.12 application to write a survey report about a question or concern using a single supported news site. The news site is used to conduct searches and read articles. Currently only the [MedicalXpress](https://medicalxpress.com/) news site is supported for medical topics, although some additional sites are planned for inclusion. Numerous calls are made to OpenAI LLMs to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

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

