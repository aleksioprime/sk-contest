import axios from 'axios'

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_BACKEND_API_URL || '/backend',
  headers: { 'Content-Type': 'application/json' },
})

export default publicApi
