"""Small gold-blind interface repairs around the original GraphLocator agents.

No JSON CIG, alternate retrieval, class expansion, or score-based selection is
introduced. Final identities use only public base AST definition anchors.
"""
from __future__ import annotations
import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
import re
import textwrap

from . import transport

_installed = None
_inventory = None


class RelevanceFormatError(transport.ProtocolError): pass


def strict_booleans(content, expected):
    """Accept only an entire, unambiguous boolean sequence of exact length."""
    text=(content or '').strip()
    fence=re.fullmatch(r'```(?:json|python|text)?\s*\n(.*?)\n```',text,re.S|re.I)
    if fence: text=fence.group(1).strip()
    parsed=None
    if text.startswith('['):
        try: parsed=json.loads(text)
        except ValueError:
            try: parsed=ast.literal_eval(text)
            except (ValueError,SyntaxError): pass
    else:
        lines=[line.strip() for line in text.splitlines() if line.strip()]
        if lines and all(line.lower() in {'true','false'} for line in lines):
            parsed=[line.lower()=='true' for line in lines]
    if (not isinstance(parsed,list) or len(parsed)!=expected or any(type(v) is not bool for v in parsed)):
        transport.record('relevance_format_error',expected=expected,raw_response=content,
                         policy='No guess, no semantic retry, never convert malformed rows to False')
        raise RelevanceFormatError(f'Expected exactly {expected} unambiguous booleans')
    return parsed


def _compile(function, source, extra):
    namespace=dict(function.__globals__);namespace.update(extra)
    exec(compile(source,f'<graphlocator_compat:{function.__name__}>','exec'),namespace)
    result=namespace[function.__name__]
    result.__qualname__=function.__qualname__
    return result


def _same_family(actual, requested):
    actual=getattr(actual,'value',actual)
    if requested in {'METHOD','FUNCTION','CONSTRUCTOR'}:
        return actual in {'METHOD','FUNCTION','CONSTRUCTOR'}
    return actual==requested


def install_compat(public_inventory=None):
    """Install scoped module/function bindings; original files are untouched."""
    global _installed,_inventory
    _inventory=public_inventory
    if _installed is not None: return copy.deepcopy(_installed)
    import llms
    import search_agent
    import causal_agent
    import prompts.search_agent_prompt as prompt
    import utils.execute_search as execute
    llms.get_llm_response=transport.get_llm_response
    llms.record=transport.record
    llms.ContextBudgetExceeded=transport.ContextBudgetExceeded
    search_agent.get_llm_response=transport.get_llm_response
    search_agent.record=transport.record
    causal_agent.get_llm_response=transport.get_llm_response
    patches={}
    old=textwrap.dedent(inspect.getsource(execute.search_node))
    new=old.replace('v.type == node_type','_same_family(v.type, node_type)')
    new=new.replace('v.type in ["METHOD", "FUNCTION"]','_same_family(v.type, "FUNCTION")')
    new=new.replace('if node_type == "METHOD":','if node_type in ("METHOD", "CONSTRUCTOR"):')
    if new==old: raise RuntimeError('Unexpected upstream search_node; family patch anchor missing')
    execute.search_node=_compile(execute.search_node,new,{'_same_family':_same_family})
    patches['method_function_family']={'before':hashlib.sha256(old.encode()).hexdigest(),
                                      'after':hashlib.sha256(new.encode()).hexdigest()}
    old_edge=textwrap.dedent(inspect.getsource(execute.search_edge));new_edge=old_edge
    replacements={
        'if src_node_type == "METHOD":':'if src_node_type in ("METHOD", "CONSTRUCTOR"):',
        'if trg_node_type == "METHOD":':'if trg_node_type in ("METHOD", "CONSTRUCTOR"):',
        'if src_node.type == NodeType.METHOD or src_node.type == NodeType.FUNCTION:':
            'if _same_family(src_node.type, "FUNCTION"):',
        'if trg_node.type == NodeType.METHOD or trg_node.type == NodeType.FUNCTION:':
            'if _same_family(trg_node.type, "FUNCTION"):',
        'v.type in ["METHOD", "FUNCTION"]':'_same_family(v.type, "FUNCTION")'}
    for before,after in replacements.items():
        if before not in new_edge: raise RuntimeError('Unexpected upstream edge family patch anchor')
        new_edge=new_edge.replace(before,after)
    execute.search_edge=_compile(execute.search_edge,new_edge,{'_same_family':_same_family})
    patches['edge_function_family']={'before':hashlib.sha256(old_edge.encode()).hexdigest(),
                                    'after':hashlib.sha256(new_edge.encode()).hexdigest(),
                                    'family':['METHOD','FUNCTION','CONSTRUCTOR'],'raw_node_types_unchanged':True}
    search_agent.SearchEdgeTool=copy.deepcopy(search_agent.SearchEdgeTool)
    description=search_agent.SearchEdgeTool['function']['description']
    search_agent.SearchEdgeTool['function']['description']=description.replace('UseBy','UsedBy')
    prompt.SearchEdgeTool=copy.deepcopy(search_agent.SearchEdgeTool)
    patches['tool_example_typo']={'replacements':description.count('UseBy'),'from':'UseBy','to':'UsedBy'}
    old=textwrap.dedent(inspect.getsource(search_agent.SearchAgent.is_relevant))
    anchor="    pattern = r'```(?:\\w+)?\\n(.*?)\\n```'"
    if anchor not in old: raise RuntimeError('Unexpected upstream relevance parser')
    new=old[:old.index(anchor)]+"    return strict_booleans(response[0][0].get('content'), len(node_list))\n"
    request_anchor='get_llm_response(self.model_name, judge_messages, with_tool=False)'
    if new.count(request_anchor)!=1: raise RuntimeError('Unexpected relevance request patch anchor')
    new=new.replace(request_anchor,'get_llm_response(self.model_name, judge_messages, with_tool=False, relevance_count=len(node_list))')
    # Change only the serialization sentences/example. The original task,
    # relevance criterion, issue, entire candidate list and candidate order stay.
    instruction=search_agent.IS_RELEVANT_INSTRUCTION
    format_anchor='Results should be separated by new lines and wrapped with ```'
    if instruction.count(format_anchor)!=1: raise RuntimeError('Unexpected relevance instruction format anchor')
    instruction=instruction[:instruction.index(format_anchor)]+(
        'Return exactly one JSON array containing one boolean for each code element, '
        'in the supplied order. Use true for relevant and false for irrelevant. '
        'The array length must equal the number of supplied code elements. '
        'Do not use Markdown code fences, numbering, or explanations.\n')
    search_agent.IS_RELEVANT_INSTRUCTION=instruction
    search_agent.SearchAgent.is_relevant=_compile(search_agent.SearchAgent.is_relevant,new,
        {'strict_booleans':strict_booleans,'get_llm_response':transport.get_llm_response})
    patches['strict_relevance_serialization']={'before':hashlib.sha256(old.encode()).hexdigest(),
        'after':hashlib.sha256(new.encode()).hexdigest(),'response_schema':'Exact-length JSON boolean array',
        'semantic_retry_requests':0,'same_issue_and_all_candidates_in_original_order':True,
        'format_instruction_sha256':hashlib.sha256(instruction.encode()).hexdigest()}
    original=causal_agent.CausalAgent.parse_mermaid_to_networkx
    old=textwrap.dedent(inspect.getsource(original));new=old
    anchors={
        "if groups['source'] not in G:":"if groups['source'] not in G or G.nodes[groups['source']].get('_compat_placeholder', False):",
        "code_element=code_elements\n": "code_element=code_elements, _compat_placeholder=False\n",
        "G.add_node(groups['target'], name='Issue', code_element=[])":
        "G.add_node(groups['target'], name='Issue', code_element=[], _compat_placeholder=True)"}
    for before,after in anchors.items():
        if new.count(before)!=1: raise RuntimeError('Unexpected Mermaid placeholder patch anchor')
        new=new.replace(before,after)
    causal_agent.CausalAgent.parse_mermaid_to_networkx=_compile(original,new,{})
    patches['mermaid_target_placeholder_definition']={'before':hashlib.sha256(old.encode()).hexdigest(),
                                                    'after':hashlib.sha256(new.encode()).hexdigest()}
    _installed={'compat_version':'graphlocator_qwen3_generic_interface_v2','patches':patches,
        'python_function_search_family':['METHOD','FUNCTION','CONSTRUCTOR'],
        'original_agents_and_mermaid_algorithm_retained':True,'gold_read':False,
        'final_identity_rule':'Public base AST exact file, kind, definition start, original leaf name; ambiguous=invalid slot'}
    transport.record('compat_installed',**_installed)
    return copy.deepcopy(_installed)


def _kind(node):
    return str(getattr(node.type,'value',node.type))


def _identity(graph,node,inventory):
    location=getattr(node,'location',None)
    root=Path(graph.repo_path).resolve()
    raw_path=getattr(location,'file_path',None) if location else None
    try:
        path=Path(raw_path)
        path=(root/path if not path.is_absolute() else path).resolve().relative_to(root).as_posix()
    except (TypeError,ValueError):
        path='__unresolved_source_path__'
    kind=_kind(node); start=getattr(location,'start_line',None)
    info={'path':path,'graph_kind':kind,'graph_name':node.name,'start_line':start,
          'end_line':getattr(location,'end_line',None),'status':'invalid_ast_identity'}
    if kind=='FILE' and path!='__unresolved_source_path__':
        info.update(status='valid_file',canonical=path);return path,info
    wanted='function' if kind in {'FUNCTION','METHOD','CONSTRUCTOR'} else 'class' if kind in {'CLASS','INTERFACE','ENUM'} else None
    candidates=[row for row in inventory.get(path,[]) if row.get('kind')==wanted
                and row.get('start_line')==start
                and row.get('qualified_name','').rsplit('.',1)[-1]==node.name]
    if len(candidates)==1:
        canonical=path+'::'+candidates[0]['qualified_name']
        info.update(status='valid_exact_ast_anchor',canonical=canonical,ast_definition=copy.deepcopy(candidates[0]))
        return canonical,info
    # Deliberately invalid canonical slot, rather than guessing a class/nested
    # owner or dropping an incorrect candidate and promoting later ranks.
    canonical=f'{path}::<unresolved_ast:{kind}:{node.name}@{start}>'
    info.update(canonical=canonical,ast_anchor_matches=len(candidates))
    return canonical,info


def standardize_result(native,graph,cig,public_inventory=None):
    """Same CIG binding/insertion order; normalize identities without gold.

    The original native_result remains separately saved by the worker. CIG
    Nodes are needed because native name strings have lost definition anchors.
    """
    inventory=public_inventory if public_inventory is not None else _inventory
    if not isinstance(inventory,dict): raise ValueError('A public base AST inventory is required')
    from rdfs.dependency_graph.models.graph_data import Node
    output={'found_files':[],'found_entities':[],'found_modules':[],'identity_validation':[]}
    def add(key,value):
        if value not in output[key]: output[key].append(value)
    for factor in cig.nodes:
        for position,node in enumerate(cig.nodes[factor].get('code_element',[])):
            if isinstance(node,str): node=Node.from_json(node)
            kind=_kind(node)
            if kind not in {'FILE','FUNCTION','METHOD','CONSTRUCTOR','CLASS','INTERFACE','ENUM'}: continue
            canonical,info=_identity(graph,node,inventory)
            info.update(factor=str(factor),binding_position=position)
            output['identity_validation'].append(info)
            path=canonical.split('::',1)[0]
            add('found_files',path)
            if kind in {'FUNCTION','METHOD','CONSTRUCTOR'}:
                add('found_entities',canonical)
                if info['status']=='valid_exact_ast_anchor':
                    qn=canonical.split('::',1)[1]
                    if '.' in qn:
                        # A nested function parent is not automatically a class.
                        parent=qn.rsplit('.',1)[0]
                        if any(r.get('kind')=='class' and r.get('qualified_name')==parent for r in inventory.get(path,[])):
                            add('found_modules',path+'::'+parent)
            elif kind in {'CLASS','INTERFACE','ENUM'}:
                add('found_modules',canonical)
    return output
