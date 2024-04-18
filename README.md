# mednewsqa
**mednewsqa** is a Python 3.12 application to generate a response to a medical question or concern using medical news. It uses [MedicalXpress](https://medicalxpress.com/) to conduct searches and read article texts. Numerous calls are made to the GPT-4 LLM to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

## Approach
1. Search terms for the given user input are listed by the LLM. The user input is a medical question or concern.
2. For each search term, a single page of search results is retrieved, sorted upstream by each of `relevancy` and `date`. The search results are filtered in batches for relevance by the LLM. This step is repeated for additional pages of search results until there are no relevant results.
3. For each filtered search result, the corresponding article text is retrieved and is condensed for relevance by the LLM.
4. All condensed texts of all filtered search results are concatenated together, up to the maximum context length of the LLM, and are provided to the LLM for formulating a list of sections for the final answer.
5. All concatenated condensed texts are provided to the LLM for formulating the text for each section of the final response.
