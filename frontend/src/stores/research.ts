import {useCallback,useEffect,useState} from 'react';
import {researchApi} from '../api/research';
import type {Run,Proposal} from '../types/domain';
export function useResearch(){const [runs,setRuns]=useState<Run[]>([]),[proposals,setProposals]=useState<Proposal[]>([]),[error,setError]=useState('');const reload=useCallback(async()=>{try{const [r,p]=await Promise.all([researchApi.runs(),researchApi.proposals()]);setRuns(r);setProposals(p);setError('');}catch(e){setError(e.message);}},[]);useEffect(()=>{reload();const timer=setInterval(reload,3000);return()=>clearInterval(timer);},[reload]);return {runs,proposals,error,reload};}
