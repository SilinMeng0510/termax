import uuid
import os.path
from typing import List, Dict

import chromadb
from chromadb.utils import embedding_functions

chromadb.logger.setLevel(chromadb.logging.ERROR)

from termax.utils.const import *
from termax.utils.metadata import *
from termax.utils import Config, CONFIG_HOME


class Memory:
    def __init__(
            self,
            data_path: str = CONFIG_HOME,
            embedding_model: str = "text-embedding-ada-002"
    ):
        """
        RAG for Termax: memory and external knowledge management.
        Args:
            data_path: the path to store the data.
            embedding_model: the embedding model to use, default will use the embedding model from ChromaDB,
             if the OpenAI has been set in the configuration, it will use the OpenAI embedding model
             "text-embedding-ada-002".
        """
        self.config = Config().read()
        self.client = chromadb.PersistentClient(path=os.path.join(data_path, DB_PATH))

        # use the OpenAI embedding function if the openai section is set in the configuration.
        if self.config.get(CONFIG_SEC_OPENAI, None):
            self.client.get_or_create_collection(
                DB_COMMAND_HISTORY,
                embedding_function=embedding_functions.OpenAIEmbeddingFunction(
                    model_name=embedding_model,
                    api_key=self.config[CONFIG_SEC_OPENAI][CONFIG_SEC_API_KEY]
                )
            )
        else:
            self.client.get_or_create_collection(DB_COMMAND_HISTORY)

    def add_query(
            self,
            queries: List[Dict[str, str]],
            collection: str = DB_COMMAND_HISTORY,
            idx: List[str] = None
    ):
        """
        add_query: add the queries to the memery.
        Args:
            queries: the queries to add to the memery. Should be in the format of
                {
                    "query": "the query",
                    "response": "the response"
                }
            collection: the name of the collection to add the queries.
            idx: the ids of the queries, should be in the same length as the queries.
            If not provided, the ids will be generated by UUID.

        Return: A list of generated IDs.
        """
        if idx:
            ids = idx
        else:
            ids = [str(uuid.uuid4()) for _ in range(len(queries))]

        query_list = [query['query'] for query in queries]
        added_time = datetime.now().isoformat()
        resp_list = [{'response': query['response'], 'created_at': added_time} for query in queries]
        # insert the record into the database
        self.client.get_or_create_collection(collection).add(
            documents=query_list,
            metadatas=resp_list,
            ids=ids
        )

        return ids

    def query(self, query_texts: List[str], collection: str = DB_COMMAND_HISTORY, n_results: int = 5):
        """
        query: query the memery.
        Args:
            query_texts: the query texts to search in the memery.
            collection: the name of the collection to search, default is the command history.
            n_results: the number of results to return.

        Returns: the top k results.
        """
        return self.client.get_or_create_collection(collection).query(query_texts=query_texts, n_results=n_results)

    def peek(self, collection: str = DB_COMMAND_HISTORY, n_results: int = 20):
        """
        peek: peek the memery.
        Args:
            collection: the name of the collection to peek, default is the command history.
            n_results: the number of results to return.

        Returns: the top k results.
        """
        return self.client.get_or_create_collection(collection).peek(limit=n_results)

    def get(self, record_id: str = None, collection: str = DB_COMMAND_HISTORY):
        """
        get: get the record by the id.
        Args:
            record_id: the id of the record.
            collection: the name of the collection to get the record.

        Returns: the record.
        """
        collection = self.client.get_collection(collection)
        if not record_id:
            return collection.get()

        return collection.get(record_id)

    def delete(self, collection_name: str = DB_COMMAND_HISTORY):
        """
        delete: delete the memery collections.
        Args:
            collection_name: the name of the collection to delete.
        """
        return self.client.delete_collection(name=collection_name)

    def count(self, collection_name: str = DB_COMMAND_HISTORY):
        """
        count: count the number of records in the memery.
        Args:
            collection_name: the name of the collection to count.
        """

        return self.client.get_collection(name=collection_name).count()

    def reset(self):
        """
        reset: reset the memory.
        Notice: You may need to set the environment variable `ALLOW_RESET` to `TRUE` to enable this function.
        """
        self.client.reset()
