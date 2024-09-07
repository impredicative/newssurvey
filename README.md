# newssurvey
**newssurvey** is a Python 3.12 application to write a survey report about a question or concern using a single supported news site. The news site is used to conduct searches and read articles. Currently only the [MedicalXpress](https://medicalxpress.com/) news site is supported for medical topics. Numerous calls are made to OpenAI LLMs to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

## Approach
Each step in this workflow corresponds to an action taken by the LLM.

1. **Get search terms**: Search terms for the given user query and site are listed by the LLM. The user query is a question or concern applicable to the user chosen news site.
2. **Get filtered search results**: For each search term, a single page of search results is retrieved. More than one search type may be supported by the site, in which case all supported search types are used. Each result is composed of a title and possibly a blurb. The search results are filtered, one page at a time, for relevance by the LLM. This step is repeated for additional pages of search results until there are no relevant results for the page. After this, the full texts of all filtered search results are read.
3. **List section names**: The list of article titles is presented to the LLM, ordered by distance to the user query. The LLM provides a coherent single-level list of sections names.
4. **Get response title**: The LLM provides the response title using the list of section names.
5. **Rate articles for sections**: For each article, the LLM numerically rates on a scale of 0 to 100 how well the article can contribute to each section.
6. **Condense article by section**: For each article and section pairing, limited to ones with nonzero ratings, the LLM condenses the article text.
7. **Get text by section**: For each section, its condensed articles are concatenated together, ordered by their corresponding ratings, up to the maximum input context length of the LLM. The LLM formulates the text for each section.
