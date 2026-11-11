import {useEffect,useState} from 'react';
export function useHash(){const [page,setPage]=useState(location.hash.slice(1)||'overview');useEffect(()=>{const change=()=>setPage(location.hash.slice(1)||'overview');window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change);},[]);return page;}
