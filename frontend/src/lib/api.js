import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 60000 });

export const chat = async ({ message, conversation_id, session_id }) => {
  const { data } = await api.post("/chat", { message, conversation_id, session_id });
  return data;
};

export const listTools = async () => (await api.get("/tools")).data.tools;
export const mcpManifest = async () => (await api.get("/mcp/manifest")).data;
export const mcpCall = async (name, args) =>
  (await api.post("/mcp/call", { name, args })).data;

export const listConversations = async () =>
  (await api.get("/conversations")).data.conversations;
export const getConversation = async (id) => (await api.get(`/conversations/${id}`)).data;
export const deleteConversation = async (id) => (await api.delete(`/conversations/${id}`)).data;

export const listMemories = async () => (await api.get("/memories")).data.memories;
export const clearMemories = async () => (await api.delete("/memories")).data;
export const deleteMemory = async (id) => (await api.delete(`/memories/${id}`)).data;

export const listNotes = async () => (await api.get("/notes")).data.notes;
export const deleteNote = async (id) => (await api.delete(`/notes/${id}`)).data;

export const health = async () => (await api.get("/health")).data;
