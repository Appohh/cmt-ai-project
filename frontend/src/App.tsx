import { AuthProvider } from './context/AuthComponent'
import { AppRouter } from './router/AppRouter'

function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  )
}

export default App
