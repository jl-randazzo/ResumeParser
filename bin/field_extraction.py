import logging

from gensim.utils import simple_preprocess

from bin import lib
from spacy.matcher import Matcher
import re

EMAIL_REGEX = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}"
PHONE_REGEX = r"\(?(\d{3})?\)?[\s\.-]{0,2}?(\d{3})[\s\.-]{0,2}(\d{4})"


def candidate_name_extractor(input_string, nlp):

    doc = nlp(input_string)

    # Extract entities
    doc_entities = doc.ents

    # Subset to person type entities
    doc_persons = filter(lambda x: x.label_ == 'PERSON', doc_entities)
    doc_persons = filter(lambda x: len(x.text.strip().split()) >= 2, doc_persons)
    doc_persons = map(lambda x: x.text.strip(), doc_persons)
    doc_persons = list(doc_persons)


    # Assuming that the first Person entity with more than two tokens is the candidate's name
    if len(doc_persons) > 0:
        print(doc_persons[0])
        return doc_persons[0]
    print("NOT FOUND")
    return "NOT FOUND"

def university_extractor(input_string, nlp):
    #Remove unnecessary spaces from file
    input_string = re.sub('\t',' ', input_string)
    input_string = re.sub(' +', ' ', input_string)

    doc = nlp(input_string)
    
    doc_propernouns = filter(lambda x: x.label_ == 'ORG', doc.ents)
    doc_propernouns = map(lambda x: x, doc_propernouns)
    doc_propernouns = list(doc_propernouns)
    doc_universities = list()
    for x in doc_propernouns: 
        for y in x.text.strip().split('\n'):
            doc_universities.append(y) 

    doc_universities = filter(lambda x: 'University' in x or 'College' in x or 'Polytechnic' in x or 'School' in x or 'State' in x
            or 'Institute' in x, doc_universities)
    doc_universities = list(doc_universities)
    doc_universities = keep_unique(doc_universities)

    if len(doc_universities) > 0:
        return doc_universities
    return ""

patterna = [{"POS": "PROPN", "OP":"?"}, {"POS": "PROPN", "OP":"?"}, 
            {"POS": "PROPN"}, {"TEXT": {"REGEX": "^[Mm]ajor$"}}]
patternb = [{"TEXT": {"REGEX": "^[Mm]ajor(ed)?$"}}, {"TEXT": ":", "OP":"*"}, {"POS": "PROPN"}, 
            {"POS": "PROPN","OP":"*"}, {"POS": "PROPN", "OP":"*"}]
patternc = [{"TEXT": {"REGEX": "^([Aa]ssociate('?s)?|[Bb]achelor('?s)?|[Mm]aster('?s)?)$"}}, {"TEXT": {"REGEX": "^(of|in)$"}}, 
            {"TEXT": {"REGEX": "^[Aa]pplied$"}, "OP":"*"},{"TEXT": {"REGEX": "^(Sciences?|Arts?)$"}, "OP": "*"},
            {"TEXT":{"REGEX":"[Dd]egree"},"OP":"*"},
            {"TEXT": {"REGEX": "^(of|in|,)$"}, "OP": "*"}, {"POS": "PROPN", "OP":"*"},{"POS": "PROPN", "OP":"*"},{"POS": "PROPN", "OP":"*"}]
patternd = [{"TEXT": {"REGEX": "(A|B|M)\.?(S|A\.?S?|B\.?A)\.?"}}, {"TEXT": {"REGEX": "^(,|:|in|of|[Dd]egree)$"}}, {"TEXT": {"REGEX": "^(in|of)$"}, "OP":"*"},
            {"POS":"PROPN", "OP":"*"},{"POS":"PROPN", "OP":"*"},{"POS":"PROPN"}]
study_pattern = [{"TEXT": {"REGEX": "^[Ss]tud(ying|ent|ies)$"}},{"TEXT": {"REGEX": "^(in|of)"}, "OP":"*"}, 
            {"POS": "PROPN", "OP":"*"},{"POS":"PROPN", "OP":"*"}, {"POS":"PROPN"}]
student_pattern = [{"TEXT": {"REGEX": "^[Ss]tudent$"}}, {"TEXT": {"REGEX": "(of|in)"}}, 
            {"POS": "PROPN", "OP":"*"},{"POS":"PROPN", "OP":"*"}, {"POS":"PROPN"}]

def major_extractor(input_string, nlp):
    #Remove unnecessary spaces from file
    input_string = re.sub('\t',' ', input_string)
    input_string = re.sub(' +',' ', input_string)
    input_string = re.sub(r'[^\x00-\x80]',' ', input_string)
    doc = nlp(input_string)
    
    for x in doc:
        print(x.text + '\\', end='')
    matcher = Matcher(nlp.vocab, True)
    matcher.add("Major", None, patterna)
    matcher.add("Majorb", None, patternb)
    matcher.add("Degreea", None, patternc)
    matcher.add("Degreeb", None, patternd)
    matcher.add("Studies", None, study_pattern)
    matcher.add("Stedent", None, student_pattern)
    matches = matcher(doc)

    out_m = list()
    
    for id, start, end in matches:
        out_m.append(doc[start:end].text)
    out_m = keep_unique(out_m)
    print('testing matches:\n')
    print(out_m)
    #input()

    if len(out_m) > 0:
        return out_m
    return ""

def extract_fields(df):
    for extractor, items_of_interest in lib.get_conf('extractors').items():
        df[extractor] = df['text'].apply(lambda x: extract_skills(x, extractor, items_of_interest))
    return df


def extract_skills(resume_text, extractor, items_of_interest):
    potential_skills_dict = dict()
    matched_skills = set()

    # TODO This skill input formatting could happen once per run, instead of once per observation.
    for skill_input in items_of_interest:

        # Format list inputs
        if type(skill_input) is list and len(skill_input) >= 1:
            potential_skills_dict[skill_input[0]] = skill_input

        # Format string inputs
        elif type(skill_input) is str:
            potential_skills_dict[skill_input] = [skill_input]
        else:
            logging.warn('Unknown skill listing type: {}. Please format as either a single string or a list of strings'
                         ''.format(skill_input))

    for (skill_name, skill_alias_list) in potential_skills_dict.items():

        skill_matches = 0
        # Iterate through aliases
        for skill_alias in skill_alias_list:
            # Add the number of matches for each alias
            skill_matches += lib.term_count(resume_text, skill_alias.lower())

        # If at least one alias is found, add skill name to set of skills
        if skill_matches > 0:
            matched_skills.add(skill_name)

    return matched_skills

def keep_unique(lst):
    unique_list = list()

    for string in lst:
        add = True
        string = re.sub(' +', ' ', string)
        string = string.strip()
        for xstring in unique_list:
            if string in xstring:
                add = False
            elif xstring in string:
                unique_list.remove(xstring)
        if add:
            unique_list.append(string)
    
    return unique_list

