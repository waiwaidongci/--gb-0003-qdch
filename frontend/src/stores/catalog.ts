import {useCallback,useEffect,useState} from 'react';
import {catalogApi} from '../api/catalog';
import type {Product,Batch} from '../types/domain';
export function useCatalog(){const [products,setProducts]=useState<Product[]>([]),[batches,setBatches]=useState<Batch[]>([]),[error,setError]=useState('');const reload=useCallback(async()=>{try{const [p,b]=await Promise.all([catalogApi.products(),catalogApi.batches()]);setProducts(p);setBatches(b);setError('');}catch(e){setError(e.message);}},[]);useEffect(()=>{reload();},[reload]);return {products,batches,error,reload};}
