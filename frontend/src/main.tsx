import React from 'react';import {createRoot} from 'react-dom/client';import {useSession} from './stores/session';import {AppRouter} from './router/AppRouter';import {Login} from './pages/Login';import './styles.css';
function App(){const session=useSession();if(session.loading)return <div className="loading">正在打开研究档案…</div>;return session.user?<AppRouter user={session.user} logout={session.logout}/>:<Login login={session.login}/>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
