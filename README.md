# mednewsqa
**mednewsqa** is a Python 3.12 application to generate a response to a medical question or topic using medical news. It uses [MedicalXpress](https://medicalxpress.com/) to conduct searches and read article texts. Numerous calls are made to the GPT-4 LLM to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

## Approach
* Search terms for the given input are listed by the LLM.
* For each search term, a single page of search results is retrieved, sorted upstream by each of `relevancy` and `date`. The search results are filtered in batches for relevance by the LLM.
* For each search term, the previous step is repeated for additional pages of search results until there are no relevant results.
* For each filtered search result, the corresponding article text is retrieved and is condensed for relevance by the LLM.
* All condensed texts of all filtered search results are concatenated together, up to the maximum context length of the LLM, and are provided to the LLM for formulating the final response.
