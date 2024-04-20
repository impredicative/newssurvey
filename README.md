# newsqa
**newsqa** (news Q&A) is a Python 3.12 application to generate a response to a question or concern using a supported news site. The specific news site is used to conduct searches and read article texts. Currently only the [MedicalXpress](https://medicalxpress.com/) is supported for medical Q&A. Numerous calls are made to the GPT-4 LLM to formulate the response. A funded [OpenAI API key](https://platform.openai.com/api-keys) is required.

## Approach
Each step in this workflow corresponds to an action taken by the LLM.

1. **Get search terms**: Search terms for the given user input are listed by the LLM. The user input is a question or concern.
2. **Get filtered search results**: For each search term, a single page of search results is retrieved, sorted upstream by each of `relevancy` and `date`. Each result is composed of a title and a blurb. The search results are filtered in batches for relevance by the LLM. This step is repeated for additional pages of search results until there are no relevant results.
3. **Get draft sections by article**: For each filtered search result, the corresponding article text is retrieved. For each text, the LLM suggests one or more single-level draft sections for the final answer, with the understanding that the text will contribute to its respective suggested sections. Each article is expected to contribute only to a subset of sections of the final answer, not necessarily to all sections.
4. **Get final sections**: A full map of all article results with their respective draft sections is presented to the LLM. The LLM suggests a coherent ordered single-level final list of sections.
5. **Get articles by section**: For each of the final sections, the LLM is given the same full map as before. The LLM lists the subset of article results that can contribute to the final section.
6. **Get notes by article and section**: A new map of all article results with their respective final sections is created. For each article-section pair, the LLM is given the text of the respective article. The LLM produces condensed notes and extracts relevant to the section from the text.
7. **Get draft response by section**: For each of the final sections, the notes for it from all mapped articles are concatenated together, up to the maximum context length of the LLM. The LLM formulates the draft response for that section. The draft responses for all sections are concatenated into the aggregated draft response.
8. **Get final response by section**: For each of the final sections, the aggregated draft response is presented to the LLM. If however the aggregated draft response is too long to fit in the context length of the LLM, an embedding of each of the individual section responses is computed. To fit the context length, individual section responses are skipped, starting with the most conceptually distant sections. The LLM outputs a final version of the response for the section. The final responses for all sections are concatenated into the aggregated final response.