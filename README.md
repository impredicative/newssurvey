# mednewsqa
**mednewsqa** is a Python 3.12 application to generate a response to a medical question or topic using medical news. It uses [Medical Xpress](https://medicalxpress.com/) to conduct searches and read article texts. Numerous calls are made to the OpenAI GPT LLM to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

## Approach

* Search terms for the given input are listed by the LLM.
* For each search term, a single page of search results are obtained, sorted by each of `relevancy` and `date`. The combined search results are filtered for relevance by the LLM.
* For each search term, this process is repeated with additional pages of search results, until there are no more search results or until the LLM finds no more results to be relevant.
* For each filtered search result, the corresponding article text is read and is independently condensed for relevance by the LLM.
* All condensed texts of all filtered search results are concatenated and are together provided to the LLM for formulating the final response.
