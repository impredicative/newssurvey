# newsqa
**newsqa** (news Q&A) is a Python 3.12 application to extensively research a question or concern using a supported news site. The specific news site is used to conduct searches and read article texts. Currently only the [MedicalXpress](https://medicalxpress.com/) news site is supported for medical topics. Numerous calls are made to OpenAI LLMs to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

## Approach
Each step in this workflow corresponds to an action taken by the LLM.

1. **Get search terms**: Search terms for the given user query and site are listed by the LLM. The user query is a question or concern applicable to the user chosen news site.
2. **Get filtered search results**: For each search term, a single page of search results is retrieved. More than one search type may be supported by the site, in which case all supported search types are used. Each result is composed of a title and possibly a blurb. The search results are filtered, one page at a time, for relevance by the LLM. This step is repeated for additional pages of search results until there are no relevant results for the page.
3. **Get draft sections by article**: For each filtered search result, the corresponding article text is retrieved. For each text, the LLM suggests one or more single-level draft sections for the final answer, with the understanding that the text will contribute to its respective suggested sections. Each article is expected to contribute only to a subset of sections of the final answer.
4. **Get final sections**: The list of draft sections is presented to the LLM. The LLM suggests a coherent single-level consolidated final list of sections. A map of articles to final sections is internally maintained.
5. **Order final sections**: The list of final sections is ordered for relevance by the LLM.
6. **Get extracts by article and section**: For each article-section pair, the LLM is given the text of the respective article. The LLM produces extracts relevant to the section from the text.
7. **Get importance by article and section**: For each article-section pair, the LLM is given the corresponding extract from the article. The LLM estimates a numerical score of each article on a scale of 0 to 100 for each of its sections.
8. **Get draft response by section**: For each of the final sections, the extracts for it from all mapped articles are concatenated together, up to the maximum context length of the LLM, limited by the descending score of each article for the section. The LLM formulates the draft response for each section.
9. **Get final response by section**: For each of the final sections, the aggregated draft response is presented to the LLM. If however the aggregated draft response is too long to fit in the context length of the LLM, an embedding of each of the individual section responses is computed. To fit the context length, individual section responses are skipped, starting with the most conceptually distant sections. The LLM outputs a final version of the response for the section. The final responses for all sections are concatenated into the aggregated final response.